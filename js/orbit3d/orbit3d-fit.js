(function (g) {
  'use strict';

  var VERSION = '70.2';
  var MARGIN = 24;
  var MIN_INNER = 40;
  var FILL_TARGET = 0.72;
  var MIN_SCALE = 0.05;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }

  function normalizeSafe(safe) {
    safe = safe || {};
    if (isFinite(safe.w) && isFinite(safe.h) && (safe.x != null || safe.y != null)) {
      return { x: num(safe.x, 0), y: num(safe.y, 0), w: Math.max(0, num(safe.w, 0)), h: Math.max(0, num(safe.h, 0)) };
    }
    var vw = num(safe.vw, 0), vh = num(safe.vh, 0);
    var left = num(safe.left, 0), right = num(safe.right, 0), top = num(safe.top, 0), bottom = num(safe.bottom, 0);
    return { x: left, y: top, w: Math.max(0, vw - left - right), h: Math.max(0, vh - top - bottom) };
  }

  function normalizeRing(ringBox) {
    ringBox = ringBox || {};
    var dist = (typeof ringBox.dist === 'number' && isFinite(ringBox.dist) && ringBox.dist > 0) ? ringBox.dist : null;
    if (isFinite(ringBox.cx) && isFinite(ringBox.cy) && isFinite(ringBox.rx) && isFinite(ringBox.ry)) {
      return { cx: +ringBox.cx, cy: +ringBox.cy, rx: Math.max(0.01, +ringBox.rx), ry: Math.max(0.01, +ringBox.ry), dist: dist };
    }
    var left = num(ringBox.left, 0), right = num(ringBox.right, 0), top = num(ringBox.top, 0), bottom = num(ringBox.bottom, 0);
    return {
      cx: (left + right) / 2, cy: (top + bottom) / 2,
      rx: Math.max(0.01, (right - left) / 2), ry: Math.max(0.01, (bottom - top) / 2),
      dist: dist
    };
  }

  function r2(v) { return Math.round(v * 100) / 100; }
  function r4(v) { return Math.round(v * 10000) / 10000; }

  function fit(safe, ringBox) {
    var S = normalizeSafe(safe);
    var R = normalizeRing(ringBox);
    var ringW = R.rx * 2, ringH = R.ry * 2;
    var safeShort = Math.min(S.w, S.h), ringShort = Math.min(ringW, ringH);

    var innerW = Math.max(MIN_INNER, S.w - MARGIN * 2);
    var innerH = Math.max(MIN_INNER, S.h - MARGIN * 2);
    var marginScale = Math.min(innerW / ringW, innerH / ringH);
    if (!isFinite(marginScale) || marginScale <= 0) marginScale = 1;

    var fillScale = (ringW > 0 && ringH > 0) ? FILL_TARGET * Math.min(S.w / ringW, S.h / ringH) : marginScale;
    if (!isFinite(fillScale) || fillScale <= 0) fillScale = marginScale;

    var noOverflowScale = Math.min(S.w / ringW, S.h / ringH);
    if (!isFinite(noOverflowScale) || noOverflowScale <= 0) noOverflowScale = marginScale;

    var scale = Math.max(marginScale, fillScale);
    scale = Math.min(scale, noOverflowScale);
    scale = Math.max(MIN_SCALE, scale);

    var targetCx = S.x + S.w / 2;
    var targetCy = S.y + S.h / 2;

    var offsetX = targetCx - R.cx;
    var offsetY = targetCy - R.cy;

    var dist = R.dist != null ? R.dist / scale : null;

    var newRingShort = ringShort * scale;
    var fillRatio = safeShort > 0 ? newRingShort / safeShort : 0;
    var marginRelaxed = scale > marginScale + 1e-9;

    return {
      dist: dist != null ? r2(dist) : null,
      offsetX: r2(offsetX),
      offsetY: r2(offsetY),
      scale: r4(scale),
      fillRatio: r4(fillRatio),
      marginRelaxed: marginRelaxed,
      safeRect: { x: r2(S.x + (S.w - innerW) / 2), y: r2(S.y + (S.h - innerH) / 2), w: r2(innerW), h: r2(innerH) }
    };
  }

  function evaluate(safe, ringBox, result) {
    var S = normalizeSafe(safe);
    var R = normalizeRing(ringBox);
    var scale = result.scale;
    var cx = R.cx + result.offsetX, cy = R.cy + result.offsetY;
    var rx = R.rx * scale, ry = R.ry * scale;
    var left = cx - rx, right = cx + rx, top = cy - ry, bottom = cy + ry;

    var visLeft = Math.max(left, S.x), visRight = Math.min(right, S.x + S.w);
    var visTop = Math.max(top, S.y), visBottom = Math.min(bottom, S.y + S.h);
    var visW = Math.max(0, visRight - visLeft), visH = Math.max(0, visBottom - visTop);
    var ringArea = Math.PI * rx * ry;
    var totalArea = Math.max(1e-6, (right - left) * (bottom - top));
    var visArea = visW * visH;
    var visibleRatio = visArea / totalArea;

    var safeCx = S.x + S.w / 2;
    var centerDeviationPct = S.w > 0 ? Math.abs(cx - safeCx) / S.w * 100 : 0;

    var margins = {
      left: left - S.x, top: top - S.y,
      right: (S.x + S.w) - right, bottom: (S.y + S.h) - bottom
    };
    var ringShort = Math.min(rx * 2, ry * 2);
    var fillRatio = safeShort > 0 ? ringShort / safeShort : 0;

    return {
      visibleRatio: r4(visibleRatio),
      centerDeviationPct: r2(centerDeviationPct),
      margins: { left: r2(margins.left), top: r2(margins.top), right: r2(margins.right), bottom: r2(margins.bottom) },
      minMargin: r2(Math.min(margins.left, margins.top, margins.right, margins.bottom)),
      fillRatio: r4(fillRatio),
      ringArea: r2(ringArea)
    };
  }

  var API = { version: VERSION, fit: fit, evaluate: evaluate };
  try { g.CLOrbit3DFit = API; } catch (e) { if (typeof module !== 'undefined' && module.exports) module.exports = API; }
})(typeof window !== 'undefined' ? window : this);
