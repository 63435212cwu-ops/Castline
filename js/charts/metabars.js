(function (g) {
  'use strict';
  var KEYS = ['咖位', '戏份', '跨度', '弧光', '张力', '暗线', '光明面', '暗黑面'];
  var EN = { 咖位: 'BILLING', 戏份: 'SCREEN', 跨度: 'SPAN', 弧光: 'ARC', 张力: 'STRIFE', 暗线: 'HIDDEN', 光明面: 'LIGHT', 暗黑面: 'DARK' };

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function finite(v) { return typeof v === 'number' && isFinite(v); }
  function num(v) {
    if (v == null || typeof v === 'boolean' || Array.isArray(v) || typeof v === 'object') return null;
    var n = Number(v);
    if (!isFinite(n)) return null;
    return Math.max(0, Math.min(100, Math.round(n)));
  }
  function text(v) { return typeof v === 'string' ? v.trim() : ''; }

  function normalize(meta) {
    if (!meta || typeof meta !== 'object' || Array.isArray(meta)) return null;
    var src = (meta.score && typeof meta.score === 'object' && !Array.isArray(meta.score)) ? meta.score : meta;
    var subSrc = (meta.sub && typeof meta.sub === 'object' && !Array.isArray(meta.sub)) ? meta.sub : {};
    var score = {}, sub = {}, known = 0;
    KEYS.forEach(function (k) {
      var s = num(src[k]);
      score[k] = s;
      if (s != null) known++;
      sub[k] = text(subSrc[k]);
    });
    return { score: score, sub: sub, known: known };
  }

  function extremes(score) {
    var hi = null, lo = null;
    KEYS.forEach(function (k) {
      var s = score[k];
      if (s == null) return;
      if (!hi || s > hi.score) hi = { key: k, score: s };
      if (!lo || s < lo.score) lo = { key: k, score: s };
    });
    return { hi: hi, lo: lo };
  }

  function summary(meta) {
    var m = normalize(meta);
    if (!m || !m.known) return '叙事位置 · 待分析';
    var ex = extremes(m.score);
    return '叙事位置 · 最高 ' + ex.hi.key + ' ' + ex.hi.score + ' · 最低 ' + ex.lo.key + ' ' + ex.lo.score;
  }

  function renderRow(k, i, m) {
    var s = m.score[k];
    if (s == null) {
      return '<div class="rm-row is-pending" data-meta="' + esc(k) + '">' +
        '<span class="rm-k">' + esc(k) + '<i class="rm-en">' + esc(EN[k]) + '</i></span>' +
        '<span class="rm-t"><i class="rm-fill" data-w="0"></i></span>' +
        '<b class="rm-v">—</b>' +
        '<small class="rm-sub">待分析</small>' +
        '</div>';
    }
    return '<div class="rm-row" data-meta="' + esc(k) + '" data-score="' + s + '">' +
      '<span class="rm-k">' + esc(k) + '<i class="rm-en">' + esc(EN[k]) + '</i></span>' +
      '<span class="rm-t" role="progressbar" aria-valuenow="' + s + '" aria-valuemin="0" aria-valuemax="100" aria-label="' + esc(k) + ' ' + s + ' 分"><i class="rm-fill" data-w="' + s + '"></i></span>' +
      '<b class="rm-v">' + s + '</b>' +
      '<small class="rm-sub">' + esc(m.sub[k] || '依据未提供') + '</small>' +
      '</div>';
  }

  function render(meta, opts) {
    opts = opts || {};
    var m = normalize(meta);
    var cls = 'radar-meta' + (opts.className ? ' ' + opts.className : '');
    var head = '<div class="rm-head"><span class="rm-title">叙事位置 · NARRATIVE</span><span class="rm-summary">' + esc(summary(meta)) + '</span></div>';
    if (!m || !m.known) {
      return '<section class="' + cls + ' is-empty" aria-label="叙事八维">' + head +
        '<p class="rm-empty">待分析：叙事位置尚未现算（图谱缺少事件/关系字段，或角色未入图）。</p></section>';
    }
    var rows = KEYS.map(function (k, i) { return renderRow(k, i, m); }).join('');
    return '<section class="' + cls + '" aria-label="叙事八维" data-known="' + m.known + '">' + head +
      '<div class="rm-rows">' + rows + '</div></section>';
  }

  g.CLRadarMeta = { KEYS: KEYS, EN: EN, render: render, summary: summary, normalize: normalize };
})(typeof window !== 'undefined' ? window : this);
