
(function (global) {
  'use strict';

  var KEYS = ['智谋', '实力', '意志', '魅力', '情感', '野心', '权势', '道义'];
  var EN = {
    智谋: 'MIND',
    实力: 'FORCE',
    意志: 'WILL',
    魅力: 'CHARM',
    情感: 'HEART',
    野心: 'DRIVE',
    权势: 'REACH',
    道义: 'CODE'
  };

  var TWENTY_EIGHT_MANSIONS = [
    { name: '角', quad: 'east', quadName: '苍龙', en: 'Jiao' },
    { name: '亢', quad: 'east', quadName: '苍龙', en: 'Kang' },
    { name: '氐', quad: 'east', quadName: '苍龙', en: 'Di' },
    { name: '房', quad: 'east', quadName: '苍龙', en: 'Fang' },
    { name: '心', quad: 'east', quadName: '苍龙', en: 'Xin' },
    { name: '尾', quad: 'east', quadName: '苍龙', en: 'Wei' },
    { name: '箕', quad: 'east', quadName: '苍龙', en: 'Ji' },
    { name: '斗', quad: 'north', quadName: '玄武', en: 'Dou' },
    { name: '牛', quad: 'north', quadName: '玄武', en: 'Niu' },
    { name: '女', quad: 'north', quadName: '玄武', en: 'Nu' },
    { name: '虚', quad: 'north', quadName: '玄武', en: 'Xu' },
    { name: '危', quad: 'north', quadName: '玄武', en: 'Wei' },
    { name: '室', quad: 'north', quadName: '玄武', en: 'Shi' },
    { name: '壁', quad: 'north', quadName: '玄武', en: 'Bi' },
    { name: '奎', quad: 'west', quadName: '白虎', en: 'Kui' },
    { name: '娄', quad: 'west', quadName: '白虎', en: 'Lou' },
    { name: '胃', quad: 'west', quadName: '白虎', en: 'Wei' },
    { name: '昴', quad: 'west', quadName: '白虎', en: 'Mao' },
    { name: '毕', quad: 'west', quadName: '白虎', en: 'Bi' },
    { name: '觜', quad: 'west', quadName: '白虎', en: 'Zui' },
    { name: '参', quad: 'west', quadName: '白虎', en: 'Shen' },
    { name: '井', quad: 'south', quadName: '朱雀', en: 'Jing' },
    { name: '鬼', quad: 'south', quadName: '朱雀', en: 'Gui' },
    { name: '柳', quad: 'south', quadName: '朱雀', en: 'Liu' },
    { name: '星', quad: 'south', quadName: '朱雀', en: 'Xing' },
    { name: '张', quad: 'south', quadName: '朱雀', en: 'Zhang' },
    { name: '翼', quad: 'south', quadName: '朱雀', en: 'Yi' },
    { name: '轸', quad: 'south', quadName: '朱雀', en: 'Zhen' }
  ];

  function safeNum(v, fallback) {
    var n = Number(v);
    return (typeof n === 'number' && isFinite(n)) ? n : (typeof fallback === 'number' ? fallback : 0);
  }

  function round(v) {
    return Math.round(safeNum(v, 0) * 100) / 100;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] || c;
    });
  }

  function sanitizeSVG(str) {
    if (typeof str !== 'string') return '';
    if (str.indexOf('NaN') !== -1 || str.indexOf('undefined') !== -1 || str.indexOf('null') !== -1) {
      str = str.replace(/\bNaN\b/g, '0').replace(/\bundefined\b/g, '0').replace(/\bnull\b/g, '');
    }
    return str;
  }

  function radialPoint(cx, cy, r, angleRad, squash) {
    var sq = safeNum(squash, 0.9);
    return [
      round(cx + Math.cos(angleRad) * r),
      round(cy + Math.sin(angleRad) * r * sq)
    ];
  }

  function pointsToStr(pts) {
    if (!Array.isArray(pts) || !pts.length) return '';
    return pts.map(function (p) {
      return round(p[0]) + ',' + round(p[1]);
    }).join(' ');
  }

  function railGeometry(R) {
    var rw = round(R * 1.54);
    var rh = round(R * 1.62);
    var c = round(R * 0.22);
    var inset = 5;
    var cIn = Math.max(2, c - 2);
    return { rw: rw, rh: rh, c: c, inset: inset, cIn: cIn, rwIn: rw - inset, rhIn: rh - inset };
  }

  function renderFrameSVG(cx, cy, R, opt) {
    opt = opt || {};
    var parsedSize = safeNum(opt.size, 320);
    cx = safeNum(cx, parsedSize / 2);
    cy = safeNum(cy, parsedSize / 2 + 4);
    R = Math.max(10, safeNum(R, parsedSize * 0.285));

    var squash = Math.max(0.1, safeNum(opt.squash, 0.9));
    var showRails = opt.showRails !== false;
    var showCrosshair = opt.showCrosshair !== false;
    var showRuler = opt.showRuler !== false;
    var showMansions = opt.showMansions !== false;
    var showBadges = opt.showBadges !== false;

    var uid = opt.idPrefix || ('cl-hf-' + Math.floor(Math.random() * 1e6).toString(36));
    var out = [];

    out.push('<g class="cl-holo-frame" data-cx="' + round(cx) + '" data-cy="' + round(cy) + '" data-r="' + round(R) + '" aria-hidden="true">');

    out.push('<defs>');
    out.push('<filter id="' + uid + '-glow" x="-30%" y="-30%" width="160%" height="160%" color-interpolation-filters="sRGB">');
    out.push('<feGaussianBlur stdDeviation="2.4" result="blur"/>');
    out.push('<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>');
    out.push('</filter>');
    out.push('<linearGradient id="' + uid + '-rail-g" x1="0" y1="0" x2="1" y2="1">');
    out.push('<stop offset="0%" stop-color="var(--signal, #ffb45c)" stop-opacity="0.32"/>');
    out.push('<stop offset="50%" stop-color="var(--mint, #7af0c8)" stop-opacity="0.22"/>');
    out.push('<stop offset="100%" stop-color="var(--violet, #a688ff)" stop-opacity="0.36"/>');
    out.push('</linearGradient>');
    out.push('</defs>');

    if (showRails) {
      var rw = round(R * 1.54);
      var rgeo = railGeometry(R);
      var rh = rgeo.rh;
      var c = rgeo.c;

      var vOuter = [
        [cx - rw + c, cy - rh],
        [cx + rw - c, cy - rh],
        [cx + rw, cy - rh + c],
        [cx + rw, cy + rh - c],
        [cx + rw - c, cy + rh],
        [cx - rw + c, cy + rh],
        [cx - rw, cy + rh - c],
        [cx - rw, cy - rh + c]
      ];

      var cIn = rgeo.cIn;
      var rwIn = rgeo.rwIn;
      var rhIn = rgeo.rhIn;
      var vInner = [
        [cx - rwIn + cIn, cy - rhIn],
        [cx + rwIn - cIn, cy - rhIn],
        [cx + rwIn, cy - rhIn + cIn],
        [cx + rwIn, cy + rhIn - cIn],
        [cx + rwIn - cIn, cy + rhIn],
        [cx - rwIn + cIn, cy + rhIn],
        [cx - rwIn, cy + rhIn - cIn],
        [cx - rwIn, cy - rhIn + cIn]
      ];

      out.push('<g class="cl-holo-rails">');
      out.push('<polygon class="cl-holo-rail cl-holo-rail-outer" points="' + pointsToStr(vOuter) + '" fill="none" stroke="var(--line-2, rgba(255,180,92,.42))" stroke-width="var(--cl-sw-rail, 1.2)" stroke-linejoin="round"/>');
      out.push('<polygon class="cl-holo-rail cl-holo-rail-inner" points="' + pointsToStr(vInner) + '" fill="none" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)" stroke-dasharray="6 4" stroke-linejoin="round"/>');

      var bk = 7;
      var cornerTL = 'M ' + round(cx - rw + c + bk) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx - rw + c) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx - rw - 2.5) + ',' + round(cy - rh + c) + ' L ' + round(cx - rw - 2.5) + ',' + round(cy - rh + c + bk);
      var cornerTR = 'M ' + round(cx + rw - c - bk) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx + rw - c) + ',' + round(cy - rh - 2.5) + ' L ' + round(cx + rw + 2.5) + ',' + round(cy - rh + c) + ' L ' + round(cx + rw + 2.5) + ',' + round(cy - rh + c + bk);
      var cornerBR = 'M ' + round(cx + rw + 2.5) + ',' + round(cy + rh - c - bk) + ' L ' + round(cx + rw + 2.5) + ',' + round(cy + rh - c) + ' L ' + round(cx + rw - c) + ',' + round(cy + rh + 2.5) + ' L ' + round(cx + rw - c - bk) + ',' + round(cy + rh + 2.5);
      var cornerBL = 'M ' + round(cx - rw - 2.5) + ',' + round(cy + rh - c - bk) + ' L ' + round(cx - rw - 2.5) + ',' + round(cy + rh - c) + ' L ' + round(cx - rw + c) + ',' + round(cy + rh + 2.5) + ' L ' + round(cx - rw + c + bk) + ',' + round(cy + rh + 2.5);

      out.push('<path class="cl-holo-rail-bracket" d="' + cornerTL + ' ' + cornerTR + ' ' + cornerBR + ' ' + cornerBL + '" fill="none" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-rail, 1.2)"/>');

      for (var vi = 0; vi < vOuter.length; vi++) {
        out.push('<circle class="cl-holo-rail-node" cx="' + vOuter[vi][0] + '" cy="' + vOuter[vi][1] + '" r="1.4" fill="var(--signal, #ffb45c)"/>');
      }

      var notchL = round(cy - rh * 0.4), notchR = round(cy + rh * 0.4);
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx - rw) + '" y1="' + notchL + '" x2="' + round(cx - rw + 4) + '" y2="' + notchL + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx - rw) + '" y1="' + notchR + '" x2="' + round(cx - rw + 4) + '" y2="' + notchR + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx + rw) + '" y1="' + notchL + '" x2="' + round(cx + rw - 4) + '" y2="' + notchL + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-rail-notch" x1="' + round(cx + rw) + '" y1="' + notchR + '" x2="' + round(cx + rw - 4) + '" y2="' + notchR + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('</g>');
    }

    if (showCrosshair) {
      var rCoreDead = round(R * 0.26);
      var CROSS_ARM = 1.06;
      var rwCross = round(R * CROSS_ARM);
      var rhCross = round(R * CROSS_ARM);

      out.push('<g class="cl-holo-crosshairs">');
      out.push('<line class="cl-holo-crosshair cl-crosshair-lng" x1="' + round(cx) + '" y1="' + round(cy - rhCross) + '" x2="' + round(cx) + '" y2="' + round(cy - rCoreDead) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-crosshair cl-crosshair-lng" x1="' + round(cx) + '" y1="' + round(cy + rCoreDead) + '" x2="' + round(cx) + '" y2="' + round(cy + rhCross) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');

      out.push('<line class="cl-holo-crosshair cl-crosshair-lat" x1="' + round(cx - rwCross) + '" y1="' + round(cy) + '" x2="' + round(cx - rCoreDead) + '" y2="' + round(cy) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      out.push('<line class="cl-holo-crosshair cl-crosshair-lat" x1="' + round(cx + rCoreDead) + '" y1="' + round(cy) + '" x2="' + round(cx + rwCross) + '" y2="' + round(cy) + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)"/>');

      var reticles = [0.38, 0.72, 1.06];
      for (var ri = 0; ri < reticles.length; ri++) {
        var rRad = round(R * reticles[ri]);
        var rRadY = round(rRad * squash);
        var isOuterReticle = ri === reticles.length - 1;
        out.push('<ellipse class="cl-holo-reticle-ring" cx="' + round(cx) + '" cy="' + round(cy) + '" rx="' + rRad + '" ry="' + rRadY + '" fill="none" stroke="' + (isOuterReticle ? 'var(--line-2, rgba(255,180,92,.42))' : 'var(--line, rgba(172,156,230,.16))') + '" stroke-width="var(--cl-sw-hair, 0.6)" ' + (isOuterReticle ? 'stroke-dasharray="3 4"' : '') + '/>');
      }

      var tickSteps = [0.5, 0.75, 1.0];
      for (var ti = 0; ti < tickSteps.length; ti++) {
        var tr = round(R * tickSteps[ti]);
        var try_ = round(tr * squash);
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx - 3) + '" y1="' + round(cy - try_) + '" x2="' + round(cx + 3) + '" y2="' + round(cy - try_) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx - 3) + '" y1="' + round(cy + try_) + '" x2="' + round(cx + 3) + '" y2="' + round(cy + try_) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx - tr) + '" y1="' + round(cy - 3) + '" x2="' + round(cx - tr) + '" y2="' + round(cy + 3) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
        out.push('<line class="cl-holo-crosshair-tick" x1="' + round(cx + tr) + '" y1="' + round(cy - 3) + '" x2="' + round(cx + tr) + '" y2="' + round(cy + 3) + '" stroke="var(--mint, #7af0c8)" stroke-width="var(--cl-sw-thin, 0.8)"/>');
      }

      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx) + '" y="' + round(cy - rhCross - 5) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LNG 000.00° // N</text>');
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx + rwCross + 6) + '" y="' + round(cy + 2.5) + '" text-anchor="start" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LAT +090.00° // E</text>');
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx) + '" y="' + round(cy + rhCross + 13) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LNG 180.00° // S</text>');
      out.push('<text class="cl-holo-crosshair-label" x="' + round(cx - rwCross - 6) + '" y="' + round(cy + 2.5) + '" text-anchor="end" font-family="var(--mono, monospace)" font-size="var(--cl-fs-xs, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">LAT -090.00° // W</text>');
      out.push('</g>');
    }

    if (showRuler) {
      out.push('<g class="cl-holo-ruler">');
      var rulerY = round(cy + R * 0.96 * squash);
      var rulerSpan = round(R * 0.88);
      var rulerStartX = round(cx - rulerSpan);
      var rulerEndX = round(cx + rulerSpan);

      out.push('<line class="cl-holo-ruler-base" x1="' + rulerStartX + '" y1="' + rulerY + '" x2="' + rulerEndX + '" y2="' + rulerY + '" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-thin, 0.8)" stroke-dasharray="1 2"/>');

      var divisions = 16;
      var step = (rulerSpan * 2) / divisions;
      for (var di = 0; di <= divisions; di++) {
        var rx = round(rulerStartX + di * step);
        var isMajor = di % 4 === 0;
        var rLen = isMajor ? 5 : 2.5;
        out.push('<line class="cl-holo-ruler-tick" x1="' + rx + '" y1="' + rulerY + '" x2="' + rx + '" y2="' + round(rulerY + rLen) + '" stroke="' + (isMajor ? 'var(--signal, #ffb45c)' : 'var(--line, rgba(172,156,230,.16))') + '" stroke-width="var(--cl-sw-hair, 0.6)"/>');
        if (isMajor) {
          var relVal = Math.round((di - divisions / 2) * 10);
          var signStr = relVal > 0 ? '+' + relVal : relVal === 0 ? '±00' : String(relVal);
          out.push('<text class="cl-holo-ruler-num" x="' + rx + '" y="' + round(rulerY + 11) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-micro, 10px)" fill="var(--ink-3, #88819d)">' + signStr + '</text>');
        }
      }

      out.push('<text class="cl-holo-ruler-meta" x="' + round(cx) + '" y="' + round(rulerY + 19) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-micro, 10px)" fill="var(--ink-3, #88819d)" letter-spacing="var(--cl-ls-mono, 0.08em)">GRID REF: [X:' + round(cx) + ' Y:' + round(cy) + '] // VERNIER: 0.05</text>');
      out.push('</g>');
    }

    if (showMansions) {
      var rMansion = round(R * 1.24);
      var rMansionY = round(rMansion * squash);

      out.push('<g class="cl-holo-mansions">');
      out.push('<ellipse class="cl-holo-mansion-ring" cx="' + round(cx) + '" cy="' + round(cy) + '" rx="' + rMansion + '" ry="' + rMansionY + '" fill="none" stroke="var(--line, rgba(172,156,230,.16))" stroke-width="var(--cl-sw-hair, 0.6)" stroke-dasharray="2 4"/>');
      out.push('<ellipse class="cl-holo-mansion-subring" cx="' + round(cx) + '" cy="' + round(cy) + '" rx="' + round(rMansion - 4) + '" ry="' + round((rMansion - 4) * squash) + '" fill="none" stroke="var(--violet, #a688ff)" stroke-opacity="0.18" stroke-width="var(--cl-sw-hair, 0.5)" stroke-dasharray="1 6"/>');

      var totalMansions = TWENTY_EIGHT_MANSIONS.length;
      for (var mi = 0; mi < totalMansions; mi++) {
        var mItem = TWENTY_EIGHT_MANSIONS[mi];
        var isQuadHead = (mi % 7 === 0);
        var theta = -Math.PI / 2 + mi * (2 * Math.PI / totalMansions);
        var cosT = Math.cos(theta);
        var sinT = Math.sin(theta);

        var rInner = isQuadHead ? rMansion - 6 : rMansion - 3;
        var rOuter = isQuadHead ? rMansion + 6 : rMansion + 3;

        var pIn = [round(cx + cosT * rInner), round(cy + sinT * rInner * squash)];
        var pOut = [round(cx + cosT * rOuter), round(cy + sinT * rOuter * squash)];

        var strokeColor = isQuadHead ? 'var(--signal, #ffb45c)' : 'var(--line, rgba(172,156,230,.16))';
        var strokeW = isQuadHead ? 'var(--cl-sw-rail, 1.2)' : 'var(--cl-sw-hair, 0.6)';
        out.push('<line class="cl-holo-mansion-tick' + (isQuadHead ? ' quad-head' : '') + '" x1="' + pIn[0] + '" y1="' + pIn[1] + '" x2="' + pOut[0] + '" y2="' + pOut[1] + '" stroke="' + strokeColor + '" stroke-width="' + strokeW + '"/>');

        if (isQuadHead) {
          out.push('<circle class="cl-holo-mansion-node" cx="' + pOut[0] + '" cy="' + pOut[1] + '" r="1.3" fill="var(--signal, #ffb45c)"/>');
        }

        var rText = rMansion + (isQuadHead ? 13 : 10);
        var pText = [round(cx + cosT * rText), round(cy + sinT * rText * squash + 2.5)];
        var textColor = isQuadHead ? 'var(--signal, #ffb45c)' : 'var(--ink-3, #88819d)';
        out.push('<text class="cl-holo-mansion-label' + (isQuadHead ? ' quad-head' : '') + '" x="' + pText[0] + '" y="' + pText[1] + '" text-anchor="middle" font-family="var(--sans, sans-serif)" font-size="var(--cl-fs-mansion, 11px)" fill="' + textColor + '">' + esc(mItem.name) + '</text>');
      }
      out.push('</g>');
    }

    if (showBadges) {
      out.push('<g class="cl-holo-badges">');

      function drawBadge(bx, by, text, align) {
        var bw = 46;
        var bh = 14;
        var cut = 3.5;
        var x0 = align === 'end' ? bx - bw : align === 'middle' ? bx - bw / 2 : bx;
        var y0 = by - bh / 2;
        x0 = round(x0);
        y0 = round(y0);

        var pts = [
          [x0 + cut, y0],
          [x0 + bw - cut, y0],
          [x0 + bw, y0 + cut],
          [x0 + bw, y0 + bh - cut],
          [x0 + bw - cut, y0 + bh],
          [x0 + cut, y0 + bh],
          [x0, y0 + bh - cut],
          [x0, y0 + cut]
        ];

        var textX = round(x0 + bw / 2);
        var textY = round(y0 + bh / 2 + 2.6);

        return '<g class="cl-holo-badge" data-code="' + esc(text) + '">' +
          '<polygon class="cl-holo-badge-frame" points="' + pointsToStr(pts) + '" fill="var(--bg, #05050b)" fill-opacity="0.82" stroke="var(--line-2, rgba(255,180,92,.42))" stroke-width="var(--cl-sw-hair, 0.7)"/>' +
          '<line class="cl-holo-badge-accent" x1="' + (x0 + 2) + '" y1="' + (y0 + 2) + '" x2="' + (x0 + cut + 2) + '" y2="' + (y0 + 2) + '" stroke="var(--signal, #ffb45c)" stroke-width="var(--cl-sw-hair, 0.7)"/>' +
          '<text class="cl-holo-badge-code" x="' + textX + '" y="' + textY + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-badge, 10px)" fill="var(--signal, #ffb45c)" letter-spacing="var(--cl-ls-mono, 0.08em)">' + esc(text) + '</text>' +
          '</g>';
      }

      var bDistW = round(R * 1.54);
      var bDistH = round(R * 1.38);

      out.push(drawBadge(cx, cy - bDistH - 8, '[SYS-GRID]', 'middle'));
      out.push(drawBadge(cx + bDistW + 6, cy, '[MK-IV]', 'start'));
      out.push(drawBadge(cx, cy + bDistH + 18, '[SYS-GRID]', 'middle'));
      out.push(drawBadge(cx - bDistW - 6, cy, '[MK-IV]', 'end'));

      var cOffsetW = round(bDistW * 0.94);
      var cOffsetH = round(bDistH * 0.94);
      out.push(drawBadge(cx - cOffsetW, cy - cOffsetH, '[MK-IV]', 'end'));
      out.push(drawBadge(cx + cOffsetW, cy - cOffsetH, '[SYS-GRID]', 'start'));
      out.push(drawBadge(cx - cOffsetW, cy + cOffsetH, '[SYS-GRID]', 'end'));
      out.push(drawBadge(cx + cOffsetW, cy + cOffsetH, '[MK-IV]', 'start'));

      out.push('</g>');
    }

    out.push('</g>');

    return sanitizeSVG(out.join(''));
  }

  function parseBenchmarkVertices(benchPoints, opt) {
    opt = opt || {};
    var cx = safeNum(opt.cx, 160);
    var cy = safeNum(opt.cy, 164);
    var R = Math.max(10, safeNum(opt.R, 91.2));
    var squash = Math.max(0.1, safeNum(opt.squash, 0.9));

    if (!benchPoints) return [];

    if (typeof benchPoints === 'string') {
      var pairs = benchPoints.trim().split(/[\s,]+/);
      var coords = [];
      for (var si = 0; si < pairs.length - 1; si += 2) {
        var px = Number(pairs[si]);
        var py = Number(pairs[si + 1]);
        if (isFinite(px) && isFinite(py)) {
          coords.push([round(px), round(py)]);
        }
      }
      return coords;
    }

    if (Array.isArray(benchPoints)) {
      if (!benchPoints.length) return [];
      if (Array.isArray(benchPoints[0])) {
        return benchPoints.map(function (p) {
          return [round(p[0]), round(p[1])];
        }).filter(function (p) {
          return isFinite(p[0]) && isFinite(p[1]);
        });
      }
      if (typeof benchPoints[0] === 'object' && benchPoints[0] !== null && 'x' in benchPoints[0] && 'y' in benchPoints[0]) {
        return benchPoints.map(function (p) {
          return [round(p.x), round(p.y)];
        }).filter(function (p) {
          return isFinite(p[0]) && isFinite(p[1]);
        });
      }
      if (typeof benchPoints[0] === 'number') {
        var ptsFromScores = [];
        var numKeys = KEYS.length;
        for (var bi = 0; bi < numKeys; bi++) {
          var sc = safeNum(benchPoints[bi], 50);
          var ang = -Math.PI / 2 + bi * (2 * Math.PI / numKeys);
          var rScale = R * Math.max(0.04, Math.min(100, sc) / 100);
          ptsFromScores.push([
            round(cx + Math.cos(ang) * rScale),
            round(cy + Math.sin(ang) * rScale * squash)
          ]);
        }
        return ptsFromScores;
      }
    }

    if (typeof benchPoints === 'object') {
      var ptsFromObj = [];
      var nKeys = KEYS.length;
      for (var ki = 0; ki < nKeys; ki++) {
        var kName = KEYS[ki];
        var val = safeNum(benchPoints[kName] != null ? benchPoints[kName] : (benchPoints[EN[kName]] != null ? benchPoints[EN[kName]] : 50), 50);
        var angle = -Math.PI / 2 + ki * (2 * Math.PI / nKeys);
        var rVal = R * Math.max(0.04, Math.min(100, val) / 100);
        ptsFromObj.push([
          round(cx + Math.cos(angle) * rVal),
          round(cy + Math.sin(angle) * rVal * squash)
        ]);
      }
      return ptsFromObj;
    }

    return [];
  }

  function renderGhostPolygon(benchPoints, opt) {
    opt = opt || {};
    var vertices = parseBenchmarkVertices(benchPoints, opt);

    if (!vertices || vertices.length < 3) {
      return '';
    }

    var ptsStr = pointsToStr(vertices);
    var showNodes = opt.showNodes !== false;
    var showLabel = !!opt.showLabel;
    var labelText = opt.labelText || 'BENCHMARK // 全书基准';

    var out = [];
    out.push('<g class="cl-ghost-layer" aria-label="全书基准幽灵轮廓" data-bench="true">');

    out.push('<polygon class="cl-ghost-glow" points="' + ptsStr + '" fill="none" stroke="var(--violet, #a688ff)" stroke-width="var(--cl-sw-glow, 3)" stroke-opacity="0.28" stroke-dasharray="var(--cl-ghost-dash, 4 3)" stroke-linejoin="round"/>');

    out.push('<polygon class="cl-ghost-fill" points="' + ptsStr + '" fill="var(--violet, #a688ff)" fill-opacity="0.06"/>');

    out.push('<polygon class="cl-ghost-polygon" points="' + ptsStr + '" fill="none" stroke="var(--violet, #a688ff)" stroke-width="var(--cl-sw-ghost, 1.4)" stroke-dasharray="var(--cl-ghost-dash, 4 3)" stroke-linejoin="round"/>');

    if (showNodes) {
      for (var ni = 0; ni < vertices.length; ni++) {
        var node = vertices[ni];
        out.push('<circle class="cl-ghost-node" cx="' + node[0] + '" cy="' + node[1] + '" r="1.8" fill="var(--violet, #a688ff)" stroke="var(--bg, #05050b)" stroke-width="0.8"/>');
      }
    }

    if (opt.heroPoints && opt.heroPoints.length === vertices.length) {
      out.push('<g class="rd-diff-mesh" aria-label="命运差值桥">');
      for (var bi = 0; bi < vertices.length; bi++) {
        var hp = opt.heroPoints[bi];
        var gp = vertices[bi];
        var hScore = (opt.scores && opt.scores[bi] != null) ? opt.scores[bi] : 50;
        var bScore = (opt.benchScores && opt.benchScores[bi] != null) ? (typeof opt.benchScores[bi] === 'object' ? opt.benchScores[bi].score : opt.benchScores[bi]) : 50;
        var delta = Math.round(hScore - bScore);
        var isSurplus = delta >= 0;
        var bridgeClass = 'rd-diff-bridge ' + (isSurplus ? 'surplus' : 'deficit');
        out.push('<line class="' + bridgeClass + '" x1="' + hp[0] + '" y1="' + hp[1] + '" x2="' + gp[0] + '" y2="' + gp[1] + '"/>');
        var mx = round((hp[0] + gp[0]) / 2);
        var my = round((hp[1] + gp[1]) / 2);
        var deltaText = (isSurplus ? '+' : '') + delta;
        out.push('<text class="rd-diff-delta ' + (isSurplus ? 'surplus' : 'deficit') + '" x="' + mx + '" y="' + my + '" text-anchor="middle" dominant-baseline="central">' + deltaText + '</text>');
      }
      out.push('</g>');
    }

    if (showLabel && vertices.length > 0) {
      var topNode = vertices[0];
      out.push('<text class="cl-ghost-label" x="' + topNode[0] + '" y="' + round(topNode[1] - 6) + '" text-anchor="middle" font-family="var(--mono, monospace)" font-size="var(--cl-fs-micro, 10px)" fill="var(--violet, #a688ff)" letter-spacing="var(--cl-ls-mono, 0.08em)">' + esc(labelText) + '</text>');
    }

    out.push('</g>');

    return sanitizeSVG(out.join(''));
  }

  function computePoints(scores, cx, cy, R, squash) {
    cx = safeNum(cx, 160);
    cy = safeNum(cy, 164);
    R = Math.max(10, safeNum(R, 91.2));
    squash = Math.max(0.1, safeNum(squash, 0.9));

    var numAxes = KEYS.length;
    var result = [];
    for (var i = 0; i < numAxes; i++) {
      var s = (Array.isArray(scores) ? scores[i] : (scores && typeof scores === 'object' ? (scores[KEYS[i]] != null ? scores[KEYS[i]] : scores[EN[KEYS[i]]]) : 0));
      var sc = safeNum(s, 0);
      var a = -Math.PI / 2 + i * (2 * Math.PI / numAxes);
      var r = R * Math.max(0.04, Math.min(100, sc) / 100);
      result.push([
        round(cx + Math.cos(a) * r),
        round(cy + Math.sin(a) * r * squash)
      ]);
    }
    return result;
  }

  function computeFrameBounds(cx, cy, R, opt) {
    cx = safeNum(cx, 160);
    cy = safeNum(cy, 164);
    R = Math.max(10, safeNum(R, 91.2));
    var squash = Math.max(0.1, safeNum(opt && opt.squash, 0.9));
    var rw = round(R * 1.58);
    var rh = round(R * 1.42 * squash);
    return {
      x: round(cx - rw),
      y: round(cy - rh),
      width: round(rw * 2),
      height: round(rh * 2)
    };
  }


  function mergeIntervals(list) {
    if (!list.length) return [];
    var s = list.slice().sort(function (a, b) { return a[0] - b[0]; });
    var out = [s[0].slice()];
    for (var i = 1; i < s.length; i++) {
      var last = out[out.length - 1];
      if (s[i][0] <= last[1] + 0.01) last[1] = Math.max(last[1], s[i][1]);
      else out.push(s[i].slice());
    }
    return out;
  }

  function complementIntervals(merged, lo, hi) {
    var out = [];
    var cur = lo;
    for (var i = 0; i < merged.length; i++) {
      var b = merged[i];
      if (b[0] > cur) out.push([cur, Math.min(b[0], hi)]);
      cur = Math.max(cur, b[1]);
      if (cur >= hi) break;
    }
    if (cur < hi) out.push([cur, hi]);
    return out.filter(function (seg) { return seg[1] - seg[0] > 0.5; });
  }

  function verticalRailPlan(edgeY0, edgeY1, bands, pad) {
    var clipped = bands.map(function (b) {
      return [Math.max(edgeY0, b[0] - pad), Math.min(edgeY1, b[1] + pad)];
    }).filter(function (b) { return b[1] > b[0]; });
    var merged = mergeIntervals(clipped);
    var covered = merged.reduce(function (s, b) { return s + (b[1] - b[0]); }, 0);
    var L = edgeY1 - edgeY0;
    var coverage = L > 0 ? covered / L : 0;
    if (coverage > 0.7) {
      var stub = L * 0.18;
      return { coverage: coverage, segs: [[edgeY0, edgeY0 + stub], [edgeY1 - stub, edgeY1]], caps: [edgeY0 + stub, edgeY1 - stub] };
    }
    var segs = complementIntervals(merged, edgeY0, edgeY1);
    var caps = [];
    segs.forEach(function (s) {
      if (s[0] > edgeY0 + 0.5) caps.push(s[0]);
      if (s[1] < edgeY1 - 0.5) caps.push(s[1]);
    });
    return { coverage: coverage, segs: segs, caps: caps };
  }

  function railBandsForSide(rects, side, cxVal) {
    return rects.filter(function (r) {
      var mid = r.x + r.width / 2;
      return side === 'left' ? mid < cxVal : mid > cxVal;
    }).map(function (r) { return [r.y, r.y + r.height]; });
  }

  function svgEl(tag, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (var k in attrs) { if (attrs.hasOwnProperty(k) && attrs[k] != null) el.setAttribute(k, attrs[k]); }
    return el;
  }

  function replaceOctagonWithFold(el, parentG, cx, cy, rw, rh, c, bandsLeft, bandsRight, pad, cls, strokeAttrs, capColor) {
    var edgeY0 = cy - rh + c, edgeY1 = cy + rh - c;
    var leftPlan = verticalRailPlan(edgeY0, edgeY1, bandsLeft, pad);
    var rightPlan = verticalRailPlan(edgeY0, edgeY1, bandsRight, pad);

    var frag = svgEl('g', { 'class': cls + '-folded' });
    var topPts = [[cx - rw, edgeY0], [cx - rw + c, cy - rh], [cx + rw - c, cy - rh], [cx + rw, edgeY0]];
    var bottomPts = [[cx + rw, edgeY1], [cx + rw - c, cy + rh], [cx - rw + c, cy + rh], [cx - rw, edgeY1]];
    var pAttrs = {};
    for (var k in strokeAttrs) if (strokeAttrs.hasOwnProperty(k)) pAttrs[k] = strokeAttrs[k];

    function addOpenPath(pts, extraCls) {
      var a = {}; for (var k2 in pAttrs) a[k2] = pAttrs[k2];
      a['class'] = cls + ' ' + extraCls;
      var d = 'M ' + round(pts[0][0]) + ',' + round(pts[0][1]);
      for (var pi = 1; pi < pts.length; pi++) d += ' L ' + round(pts[pi][0]) + ',' + round(pts[pi][1]);
      a.d = d;
      frag.appendChild(svgEl('path', a));
    }
    function addVSeg(x, y0, y1, extraCls) {
      var a = {}; for (var k3 in pAttrs) a[k3] = pAttrs[k3];
      a['class'] = cls + ' ' + extraCls; a.x1 = round(x); a.y1 = round(y0); a.x2 = round(x); a.y2 = round(y1);
      frag.appendChild(svgEl('line', a));
    }
    function addCap(x, y) {
      frag.appendChild(svgEl('circle', { 'class': 'cl-holo-rail-cap', cx: round(x), cy: round(y), r: 0.6, fill: capColor }));
    }

    addOpenPath(topPts, 'cl-holo-rail-top');
    addOpenPath(bottomPts, 'cl-holo-rail-bottom');
    leftPlan.segs.forEach(function (s) { addVSeg(cx - rw, s[0], s[1], 'cl-holo-rail-vseg cl-holo-rail-vseg-l'); });
    rightPlan.segs.forEach(function (s) { addVSeg(cx + rw, s[0], s[1], 'cl-holo-rail-vseg cl-holo-rail-vseg-r'); });
    leftPlan.caps.forEach(function (y) { addCap(cx - rw, y); });
    rightPlan.caps.forEach(function (y) { addCap(cx + rw, y); });

    parentG.replaceChild(frag, el);
    return { left: leftPlan, right: rightPlan };
  }

  function bandOverlaps(y0, y1, bands, pad) {
    for (var i = 0; i < bands.length; i++) {
      if (bands[i][1] + pad > y0 && bands[i][0] - pad < y1) return true;
    }
    return false;
  }

  function foldBracket(bracketEl, railsG, cx, cy, rgeo, bandsLeft, bandsRight, pad) {
    var rw = rgeo.rw, rh = rgeo.rh, c = rgeo.c, bk = 7;
    var corners = [
      { p: [[cx - rw + c + bk, cy - rh - 2.5], [cx - rw + c, cy - rh - 2.5], [cx - rw - 2.5, cy - rh + c], [cx - rw - 2.5, cy - rh + c + bk]], stub: 'last', side: 'left' },
      { p: [[cx + rw - c - bk, cy - rh - 2.5], [cx + rw - c, cy - rh - 2.5], [cx + rw + 2.5, cy - rh + c], [cx + rw + 2.5, cy - rh + c + bk]], stub: 'last', side: 'right' },
      { p: [[cx + rw + 2.5, cy + rh - c - bk], [cx + rw + 2.5, cy + rh - c], [cx + rw - c, cy + rh + 2.5], [cx + rw - c - bk, cy + rh + 2.5]], stub: 'first', side: 'right' },
      { p: [[cx - rw - 2.5, cy + rh - c - bk], [cx - rw - 2.5, cy + rh - c], [cx - rw + c, cy + rh + 2.5], [cx - rw + c + bk, cy + rh + 2.5]], stub: 'first', side: 'left' }
    ];
    var d = '';
    var caps = [];
    corners.forEach(function (co) {
      var pts = co.p;
      var bands = co.side === 'left' ? bandsLeft : bandsRight;
      var stubA = co.stub === 'last' ? pts[2] : pts[0];
      var stubB = co.stub === 'last' ? pts[3] : pts[1];
      var y0 = Math.min(stubA[1], stubB[1]), y1 = Math.max(stubA[1], stubB[1]);
      var intrudes = bandOverlaps(y0, y1, bands, pad);
      var kept = intrudes ? (co.stub === 'last' ? pts.slice(0, 3) : pts.slice(1, 4)) : pts;
      d += 'M ' + round(kept[0][0]) + ',' + round(kept[0][1]);
      for (var i = 1; i < kept.length; i++) d += ' L ' + round(kept[i][0]) + ',' + round(kept[i][1]);
      d += ' ';
      if (intrudes) caps.push(stubA);
    });
    bracketEl.setAttribute('d', d.trim());
    caps.forEach(function (pt) {
      railsG.appendChild(svgEl('circle', { 'class': 'cl-holo-rail-cap', cx: round(pt[0]), cy: round(pt[1]), r: 0.6, fill: 'var(--mint, #7af0c8)' }));
    });
  }

  function trimSegmentAgainstRects(ax, ay, bx, by, rects, pad) {
    var dx = bx - ax, dy = by - ay;
    var intervals = [];
    for (var i = 0; i < rects.length; i++) {
      var r = rects[i];
      var rx0 = r.x - pad, ry0 = r.y - pad, rx1 = r.x + r.width + pad, ry1 = r.y + r.height + pad;
      var t0 = 0, t1 = 1, ok = true;
      function clip(p, q) {
        if (Math.abs(p) < 1e-9) return q >= 0;
        var t = q / p;
        if (p < 0) { if (t > t1) return false; if (t > t0) t0 = t; }
        else { if (t < t0) return false; if (t < t1) t1 = t; }
        return true;
      }
      ok = clip(-dx, ax - rx0) && clip(dx, rx1 - ax) && clip(-dy, ay - ry0) && clip(dy, ry1 - ay);
      if (ok && t0 < t1) intervals.push([Math.max(0, t0), Math.min(1, t1)]);
    }
    if (!intervals.length) return { x1: ax, y1: ay, x2: bx, y2: by };
    var merged = mergeIntervals(intervals);
    var survivors = complementIntervals(merged, 0, 1);
    if (!survivors.length) return null;
    var best = survivors[survivors.length - 1];
    return { x1: round(ax + dx * best[0]), y1: round(ay + dy * best[0]), x2: round(ax + dx * best[1]), y2: round(ay + dy * best[1]) };
  }

  function foldMansionTicks(mansionsG, rects) {
    var ticks = mansionsG.querySelectorAll('.cl-holo-mansion-tick');
    var PAD = 2;
    for (var i = 0; i < ticks.length; i++) {
      var t = ticks[i];
      var x1 = +t.getAttribute('x1'), y1 = +t.getAttribute('y1');
      var x2 = +t.getAttribute('x2'), y2 = +t.getAttribute('y2');
      var node = t.nextElementSibling;
      var hasNode = node && node.classList && node.classList.contains('cl-holo-mansion-node');
      var trimmed = trimSegmentAgainstRects(x1, y1, x2, y2, rects, PAD);
      if (!trimmed) {
        if (hasNode && node.parentNode) node.parentNode.removeChild(node);
        if (t.parentNode) t.parentNode.removeChild(t);
        continue;
      }
      if (hasNode && (trimmed.x2 !== x2 || trimmed.y2 !== y2)) {
        node.setAttribute('cx', trimmed.x2);
        node.setAttribute('cy', trimmed.y2);
      }
      t.setAttribute('x1', trimmed.x1); t.setAttribute('y1', trimmed.y1);
      t.setAttribute('x2', trimmed.x2); t.setAttribute('y2', trimmed.y2);
    }
  }

  function foldOneFrame(hf) {
    if (!hf || hf.getAttribute('data-r5e-folded') === '1') return;
    var svg = hf.ownerSVGElement || (hf.closest && hf.closest('svg'));
    if (!svg) return;
    var railsG = hf.querySelector('.cl-holo-rails');
    var mansionsG = hf.querySelector('.cl-holo-mansions');
    if (!railsG && !mansionsG) return;

    var cx = safeNum(hf.getAttribute('data-cx'), 0);
    var cy = safeNum(hf.getAttribute('data-cy'), 0);
    var R = safeNum(hf.getAttribute('data-r'), 0);
    if (!R) return;

    var chipEls = svg.querySelectorAll('.rd-lab rect.rd-chip');
    if (!chipEls.length) return;
    var rects = [];
    for (var i = 0; i < chipEls.length; i++) {
      try {
        var bb = chipEls[i].getBBox();
        rects.push({ x: bb.x, y: bb.y, width: bb.width, height: bb.height });
      } catch (e) {  }
    }
    hf.setAttribute('data-r5e-folded', '1');
    if (!rects.length) return;

    if (railsG) {
      var rgeo = railGeometry(R);
      var pad = 6;
      var bandsLeft = railBandsForSide(rects, 'left', cx);
      var bandsRight = railBandsForSide(rects, 'right', cx);
      var outerEl = railsG.querySelector('.cl-holo-rail-outer');
      var innerEl = railsG.querySelector('.cl-holo-rail-inner');
      var bracketEl = railsG.querySelector('.cl-holo-rail-bracket');
      if (outerEl) {
        replaceOctagonWithFold(outerEl, railsG, cx, cy, rgeo.rw, rgeo.rh, rgeo.c, bandsLeft, bandsRight, pad,
          'cl-holo-rail cl-holo-rail-outer',
          { fill: 'none', stroke: 'var(--line-2, rgba(255,180,92,.42))', 'stroke-width': 'var(--cl-sw-rail, 1.2)', 'stroke-linejoin': 'round' },
          'var(--signal, #ffb45c)');
      }
      if (innerEl) {
        replaceOctagonWithFold(innerEl, railsG, cx, cy, rgeo.rwIn, rgeo.rhIn, rgeo.cIn, bandsLeft, bandsRight, pad,
          'cl-holo-rail cl-holo-rail-inner',
          { fill: 'none', stroke: 'var(--line, rgba(172,156,230,.16))', 'stroke-width': 'var(--cl-sw-thin, 0.8)', 'stroke-dasharray': '6 4', 'stroke-linejoin': 'round' },
          'var(--mint, #7af0c8)');
      }
      if (bracketEl) foldBracket(bracketEl, railsG, cx, cy, rgeo, bandsLeft, bandsRight, pad);
    }
    if (mansionsG) foldMansionTicks(mansionsG, rects);
  }

  function foldAllFrames(root) {
    var scope = root || (typeof document !== 'undefined' ? document : null);
    if (!scope || typeof scope.querySelectorAll !== 'function') return 0;
    var frames = scope.querySelectorAll('.cl-holo-frame:not([data-r5e-folded])');
    var n = 0;
    for (var i = 0; i < frames.length; i++) {
      try { foldOneFrame(frames[i]); n++; } catch (e) {  }
    }
    return n;
  }

  if (typeof document !== 'undefined' && typeof MutationObserver !== 'undefined') {
    (function installR5EFold() {
      var scheduled = false;
      var observer = new MutationObserver(function () {
        if (scheduled) return;
        if (!document.querySelector(".cl-holo-frame:not([data-r5e-folded])")) return;
        scheduled = true;
        var run = function () { scheduled = false; foldAllFrames(document); };
        if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run); else run();
      });
      var install = function () {
        observer.observe(document.documentElement, { childList: true, subtree: true });
        foldAllFrames(document);
      };
      if (document.documentElement) install();
      else document.addEventListener('DOMContentLoaded', install);
    })();
  }

  var CLRadarHoloFrame = {
    KEYS: KEYS,
    EN: EN,
    TWENTY_EIGHT_MANSIONS: TWENTY_EIGHT_MANSIONS,
    renderFrameSVG: renderFrameSVG,
    renderGhostPolygon: renderGhostPolygon,
    computePoints: computePoints,
    computeFrameBounds: computeFrameBounds,
    parseBenchmarkVertices: parseBenchmarkVertices,
    safeNum: safeNum,
    round: round,
    sanitizeSVG: sanitizeSVG,
    railGeometry: railGeometry,
    foldAllFrames: foldAllFrames
  };

  if (typeof window !== 'undefined') {
    window.CLRadarHoloFrame = CLRadarHoloFrame;
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = CLRadarHoloFrame;
  }
  if (typeof global !== 'undefined') {
    global.CLRadarHoloFrame = CLRadarHoloFrame;
  }

})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
