/* Castline · metabars.js — 叙事八维迷你谱 (window.CLRadarMeta)
 * @contract v71 · W3 U09 叙事八维进右坞
 * 数据源：scene 门面 S.metaOf(name)（js/scene.js:1303 → js/core/scene-core.js computeMeta），
 * 返回 { v:{key:0..1}, score:{key:0-100 整数}, sub:{key:依据副行}, ec, rc }。
 * 本模块只读这份现算结果：缺维/全缺一律「待分析」空态，不编造分值。
 * 视觉与右坞八维明细条（radar-bars-enhanced）同源：薄荷/琥珀令牌、mono 字、细描边；
 * 零 inline style——条宽经 data-w 属性由 css/radar-meta.css 的静态规则给出。
 *
 * API：
 *   CLRadarMeta.render(meta, opts)  → HTML 字符串（8 行迷你条 + 标题行 + 总评）
 *   CLRadarMeta.summary(meta)       → 纯文本一行摘要（最高维 + 最低维），供读数条使用
 *   CLRadarMeta.normalize(meta)     → { score, sub, known } 规范化（契约测试与宿主共用）
 *   CLRadarMeta.KEYS / CLRadarMeta.EN
 */
(function (g) {
  'use strict';
  /* 与 js/core/scene-mats.js META_KEYS / META_EN 保持一致（同源常量，不反向依赖 3D 模块） */
  var KEYS = ['咖位', '戏份', '跨度', '弧光', '张力', '暗线', '光明面', '暗黑面'];
  var EN = { 咖位: 'BILLING', 戏份: 'SCREEN', 跨度: 'SPAN', 弧光: 'ARC', 张力: 'STRIFE', 暗线: 'HIDDEN', 光明面: 'LIGHT', 暗黑面: 'DARK' };

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function finite(v) { return typeof v === 'number' && isFinite(v); }
  /* 只接受有限数值（数值字符串也认，与 CLRadar.scoreOf 同口径）；其余一律 null = 待分析 */
  function num(v) {
    if (v == null || typeof v === 'boolean' || Array.isArray(v) || typeof v === 'object') return null;
    var n = Number(v);
    if (!isFinite(n)) return null;
    return Math.max(0, Math.min(100, Math.round(n)));
  }
  function text(v) { return typeof v === 'string' ? v.trim() : ''; }

  /** 规范化输入：兼容 computeMeta 产物（{score, sub, ...}）与裸分值字典；缺维记 null */
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

  /** 最高/最低维：只在已评分维里取；同分按 KEYS 原序（确定性 tie-break） */
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

  /** 一行纯文本摘要：「叙事位置 · 最高 咖位 92 · 最低 暗线 8」；全缺时「叙事位置 · 待分析」 */
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

  /**
   * render(meta, opts) → HTML 字符串
   * opts.className 追加容器类；全缺时渲染「待分析」空态（不编造分值）。
   */
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
