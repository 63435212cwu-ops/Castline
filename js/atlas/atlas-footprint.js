/* Castline · atlas-footprint.js — 角色剧情线足迹面板（右坞「剧情线」标签页）· window.CLAtlasFootprint
 * @role component · @owns js/atlas/atlas-footprint.js · @contract v70
 *
 * 它回答什么：给一个角色名，答「参与几条线 · 几件事 · 第几章首次/最后」，
 * 逐线答「份量（lead/core/minor）· 状态帽 · 第几章进出这条线 · 参与位置刻度」。
 * 只读 CLAtlasModel.build() 产出的 model（CONTRACT §1）与 model.events[].cast/
 * lineIds 已声明字段；缺字段一律显示「未提供」，不推断、不用颜色/默认值补齐。
 *
 * U01/U10 并行，本文件独立于它们是否已落地：
 *   · CLAtlasModel.footprint(model,name)（U01）在场就取其 lineId/role 归属作权威名单；
 *     缺席时按契约 §1 自己扫 model.events[].cast/lineIds 求出同一个名单（见 memberLineIds）。
 *     无论哪种来源，参与位置刻度（画在迷你参与带上的每一格）永远重新扫 model.events 求出
 *     ——footprint() 只给 first/last 端点和计数，不给完整下标数组，画刻度必须自己扫。
 *   · CLAtlasGlyphs.use(kind,cls)（U10）在场就直接用其符号表；缺席时用文字/几何符号占位
 *     （FALLBACK_GLYPH），绝不假装有符号表。
 *
 * 零内联样式：迷你参与带（该角色在这条线里的事件位置 + 线跨度底色）整条走 SVG 几何属性
 * （viewBox/x/width/cx/cy），不写一次内联 style 属性，符合 tests/inline_style_lint.py 对新文件
 * 的 ratchet（新文件基线是 0，写一次就永久红）。
 *
 * 出口：window.CLAtlasFootprint = { mount, render, VERSION }
 */
(function (g) {
  'use strict';

  var VERSION = '7.0';
  var doc = g.document;

  // ---------------------------------------------------------------- 小工具
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function isArr(v) { return Object.prototype.toString.call(v) === '[object Array]'; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  var STATUS_LABEL = { resolved: '已收束', suspended: '悬置', open: '未定', conflict: '冲突', unknown: '未知' };
  var STATUS_GLYPH = { resolved: 'end-resolved', suspended: 'end-suspended', open: 'end-open', conflict: 'end-unknown', unknown: 'end-unknown' };
  var ROLE_LABEL = { lead: '领衔', core: '核心', minor: '次要' };
  // U10 CLAtlasGlyphs 缺席时的极简占位：文字/几何符号，不发明新形状语言，只求「文字+符号」可辨。
  var FALLBACK_GLYPH = {
    'end-resolved': '●', 'end-suspended': '○', 'end-open': '┄', 'end-unknown': '?',
    lead: '◆', core: '●', minor: '·'
  };

  function glyph(kind, cls) {
    if (g.CLAtlasGlyphs && typeof g.CLAtlasGlyphs.use === 'function') {
      try { var s = g.CLAtlasGlyphs.use(kind, cls); if (s) return s; } catch (e) { /* 符号表异常不阻塞渲染 */ }
    }
    var t = FALLBACK_GLYPH[kind] || '?';
    return '<i class="cl-g cl-g-fallback' + (cls ? ' ' + esc(cls) : '') + '" data-g="' + esc(kind) + '" aria-hidden="true">' + esc(t) + '</i>';
  }

  // ---------------------------------------------------------------- footprint 归属名单
  // 优先用 CLAtlasModel.footprint()（U01）给出的权威 lineId 名单；缺席/异常时自扫 model.events。
  function memberLineIds(model, events, name) {
    var ids = [], seen = {}, i, j;
    var api = g.CLAtlasModel && typeof g.CLAtlasModel.footprint === 'function' ? g.CLAtlasModel.footprint : null;
    if (api) {
      try {
        var fp = api(model, name);
        if (fp && isArr(fp.lines)) {
          for (i = 0; i < fp.lines.length; i++) {
            var lid = fp.lines[i] && fp.lines[i].lineId;
            if (lid == null) { continue; }
            var key = (typeof lid) + ':' + lid;
            if (!seen[key]) { seen[key] = true; ids.push(lid); }
          }
        }
      } catch (e) { /* 权威名单异常时退回自扫，不整体报废 */ }
    }
    if (ids.length) { return ids; }
    for (i = 0; i < events.length; i++) {
      var ev = events[i];
      if (!ev) { continue; }
      var cast = isArr(ev.cast) ? ev.cast : [];
      if (cast.indexOf(name) < 0) { continue; }
      var lineIds = isArr(ev.lineIds) ? ev.lineIds : [];
      for (j = 0; j < lineIds.length; j++) {
        var id2 = lineIds[j];
        if (id2 == null) { continue; }
        var key2 = (typeof id2) + ':' + id2;
        if (!seen[key2]) { seen[key2] = true; ids.push(id2); }
      }
    }
    return ids;
  }

  function findLineById(lines, id) {
    for (var i = 0; i < lines.length; i++) { if (lines[i] && lines[i].id === id) { return lines[i]; } }
    return null;
  }

  // 这个角色在这条线里实际参与的事件下标（按 model.events 原始顺序，不是叙事 order）。
  function charEventsInLine(events, lineId, name) {
    var out = [];
    for (var i = 0; i < events.length; i++) {
      var ev = events[i];
      if (!ev) { continue; }
      var cast = isArr(ev.cast) ? ev.cast : [];
      if (cast.indexOf(name) < 0) { continue; }
      var lineIds = isArr(ev.lineIds) ? ev.lineIds : [];
      if (lineIds.indexOf(lineId) < 0) { continue; }
      out.push(i);
    }
    return out;
  }

  function roleFor(line, name) {
    var cast = (line && isArr(line.cast)) ? line.cast : [];
    for (var i = 0; i < cast.length; i++) {
      if (cast[i] && cast[i].name === name) { return ROLE_LABEL[cast[i].role] ? cast[i].role : 'minor'; }
    }
    return 'minor';
  }

  // 用叙事 order 求这批下标里最早/最晚的两个（order 缺失时退回收集顺序，不假装有序）。
  function firstLastByOrder(events, idxs) {
    var first = idxs[0], last = idxs[0], minOrd = null, maxOrd = null, i, ev;
    for (i = 0; i < idxs.length; i++) {
      ev = events[idxs[i]];
      if (!ev || !isNum(ev.order)) { continue; }
      if (minOrd === null || ev.order < minOrd) { minOrd = ev.order; first = idxs[i]; }
      if (maxOrd === null || ev.order > maxOrd) { maxOrd = ev.order; last = idxs[i]; }
    }
    return { first: first, last: last };
  }

  // 组装本模块自用的 footprint 视图：每条线 = {lineId, line, role, mine[], entryChap, exitChap}
  function footprintOf(model, name) {
    var result = { lines: [], eventCount: 0, unionEvents: {} };
    if (!model || name == null || name === '') { return result; }
    var events = isArr(model.events) ? model.events : [];
    var lines = isArr(model.lines) ? model.lines : [];
    var lineIds = memberLineIds(model, events, name);
    for (var m = 0; m < lineIds.length; m++) {
      var lid = lineIds[m];
      var line = findLineById(lines, lid);
      var mine = charEventsInLine(events, lid, name);
      if (!mine.length) { continue; }
      var role = roleFor(line, name);
      var ends = firstLastByOrder(events, mine);
      var firstEv = events[ends.first], lastEv = events[ends.last];
      for (var mm = 0; mm < mine.length; mm++) { result.unionEvents[mine[mm]] = true; }
      result.lines.push({
        lineId: lid, line: line, role: role, mine: mine,
        entryChap: (firstEv && isNum(firstEv.chapIdx)) ? firstEv.chapIdx : null,
        exitChap: (lastEv && isNum(lastEv.chapIdx)) ? lastEv.chapIdx : null
      });
    }
    var n = 0, k;
    for (k in result.unionEvents) { if (Object.prototype.hasOwnProperty.call(result.unionEvents, k)) { n++; } }
    result.eventCount = n;
    return result;
  }

  function overallChapRange(model, fp) {
    var events = isArr(model.events) ? model.events : [];
    var min = null, max = null, k, ev;
    for (k in fp.unionEvents) {
      if (!Object.prototype.hasOwnProperty.call(fp.unionEvents, k)) { continue; }
      ev = events[Number(k)];
      if (!ev || !isNum(ev.chapIdx)) { continue; }
      if (min === null || ev.chapIdx < min) { min = ev.chapIdx; }
      if (max === null || ev.chapIdx > max) { max = ev.chapIdx; }
    }
    return { min: min, max: max };
  }

  // 1-based 展示号：chapIdx 是真实字段，+1 只是显示换算，不是发明数据。
  function chapNo(idx) { return idx + 1; }

  // ---------------------------------------------------------------- 参与位置轴（与章轴对齐）
  // 用全书 model.events 里真实出现过的 chapIdx（缺席时退到 order）算出一条全局轴，
  // 所有行共享同一条轴，位置才可跨行比较——不是按每行自己的跨度各自归一。
  function computeAxis(model) {
    var events = isArr(model.events) ? model.events : [];
    var chapVals = [], ordVals = [], i, ev;
    for (i = 0; i < events.length; i++) {
      ev = events[i];
      if (!ev) { continue; }
      if (isNum(ev.chapIdx)) { chapVals.push(ev.chapIdx); }
      if (isNum(ev.order)) { ordVals.push(ev.order); }
    }
    var mode = null, min = null, max = null;
    if (chapVals.length) { mode = 'chap'; min = Math.min.apply(null, chapVals); max = Math.max.apply(null, chapVals); }
    else if (ordVals.length) { mode = 'order'; min = Math.min.apply(null, ordVals); max = Math.max.apply(null, ordVals); }
    if (mode === null) { return null; }
    return { mode: mode, min: min, max: max, span: (max - min) || 1 };
  }

  function axisValue(axis, ev) { return axis.mode === 'chap' ? ev.chapIdx : ev.order; }
  function pct(v, axis) { return (v - axis.min) / axis.span * 100; }

  // 线的整体跨度（背景底色）：优先用 model.lines[].span（U01 已算好且 known），
  // 缺席/未知时退到该线自己 eventIdxs 的真实 chapIdx/order 极值；再拿不到就不画底色。
  function lineAxisRange(model, line, axis) {
    if (!line) { return null; }
    if (axis.mode === 'chap' && line.span && line.span.known && isNum(line.span.startChap) && isNum(line.span.endChap)) {
      return { start: line.span.startChap, end: line.span.endChap };
    }
    var events = isArr(model.events) ? model.events : [];
    var idxs = isArr(line.eventIdxs) ? line.eventIdxs : [];
    var min = null, max = null, i, ev, v;
    for (i = 0; i < idxs.length; i++) {
      ev = events[idxs[i]];
      if (!ev) { continue; }
      v = axisValue(axis, ev);
      if (!isNum(v)) { continue; }
      if (min === null || v < min) { min = v; }
      if (max === null || v > max) { max = v; }
    }
    if (min === null) { return null; }
    return { start: min, end: max };
  }

  // ---------------------------------------------------------------- 渲染
  function idAttrs(attrName, id) {
    var isNumId = typeof id === 'number';
    return attrName + '="' + esc(String(id)) + '" ' + attrName + '-num="' + (isNumId ? '1' : '0') + '"';
  }

  function renderStrip(model, line, r, axis) {
    if (!axis) {
      return '<div class="af-strip af-strip-unknown">参与位置未提供</div>';
    }
    var events = isArr(model.events) ? model.events : [];
    var range = lineAxisRange(model, line, axis);
    var bg = '';
    if (range) {
      var x0 = pct(range.start, axis), x1 = pct(range.end, axis);
      var w = Math.max(x1 - x0, 0.8);
      bg = '<rect class="af-strip-bg" x="' + x0.toFixed(2) + '" width="' + w.toFixed(2) + '" y="3" height="4" rx="1"></rect>';
    }
    var ticks = [];
    for (var i = 0; i < r.mine.length; i++) {
      var idx = r.mine[i], ev = events[idx];
      if (!ev) { continue; }
      var v = axisValue(axis, ev);
      if (!isNum(v)) { continue; }
      var x = pct(v, axis);
      var label = (isNum(ev.chapIdx) ? ('第' + chapNo(ev.chapIdx) + '章') : '章节未提供') + (ev.title ? ' · ' + ev.title : '');
      ticks.push('<circle class="af-tick" data-act="event" data-event-idx="' + idx + '" tabindex="0" role="button" aria-label="' + esc(label) + '" cx="' + x.toFixed(2) + '" cy="5" r="1.7"></circle>');
    }
    return '<svg class="af-strip" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="参与位置刻度">' + bg + ticks.join('') + '</svg>';
  }

  function renderRow(model, r, axis) {
    var line = r.line || {};
    var status = (line.statusKnown === false || !STATUS_LABEL[line.status]) ? 'unknown' : line.status;
    var statusLabel = STATUS_LABEL[status] || STATUS_LABEL.unknown;
    var cap = glyph(STATUS_GLYPH[status] || 'end-unknown', 'af-cap-g');
    var genClass = isNum(line.gen) ? ('gen-' + (((line.gen % 6) + 6) % 6)) : 'gen-x';
    var lineName = (line.nameKnown === false || !line.name) ? ('未命名线 · #' + String(r.lineId)) : String(line.name);
    var roleGlyph = glyph(r.role, 'af-role-g');
    var roleLabel = ROLE_LABEL[r.role] || ROLE_LABEL.minor;
    var spanTxt = (r.entryChap != null && r.exitChap != null)
      ? ('第' + chapNo(r.entryChap) + '–' + chapNo(r.exitChap) + '章 · ' + r.mine.length + ' 事')
      : (r.mine.length + ' 事 · 章跨未提供');
    var ariaRow = lineName + '：' + roleLabel + '参与 · 状态' + statusLabel + ' · ' + spanTxt;
    var strip = renderStrip(model, line, r, axis);
    return '<li class="af-line ' + genClass + '" role="listitem" aria-label="' + esc(ariaRow) + '">' +
      '<span class="af-cap af-status-' + esc(status) + '" title="' + esc(statusLabel) + '">' + cap + '<b class="af-cap-label">' + esc(statusLabel) + '</b></span>' +
      '<button type="button" class="af-linebtn" data-act="line" ' + idAttrs('data-line-id', r.lineId) + '><span class="af-name">' + esc(lineName) + '</span></button>' +
      '<span class="af-role af-role-' + esc(r.role) + '">' + roleGlyph + '<b class="af-role-label">' + esc(roleLabel) + '</b></span>' +
      '<span class="af-span">' + esc(spanTxt) + '</span>' +
      strip +
      '</li>';
  }

  function emptyMarkup(name) {
    return '<section class="atlas-footprint is-empty" aria-label="' + esc(name || '') + ' 的剧情线足迹">' +
      '<p class="af-empty">' + esc(name || '（未选择角色）') + ' 未在任何剧情线的事件中出现</p></section>';
  }

  /** render(model, character) → HTML 字符串（契约 §2：纯函数，供测试与 mount 共用）。 */
  function render(model, character) {
    var name = character == null ? '' : String(character);
    if (!model || !isArr(model.lines) || !isArr(model.events)) {
      return '<section class="atlas-footprint is-empty" aria-label="剧情线足迹（数据未提供）"><p class="af-empty">模型未提供，无法计算剧情线足迹。</p></section>';
    }
    var fp = footprintOf(model, name);
    if (!fp.lines.length) { return emptyMarkup(name); }
    var axis = computeAxis(model);
    var range = overallChapRange(model, fp);
    var firstTxt = range.min != null ? ('第' + chapNo(range.min) + '章首次') : '首次章节未提供';
    var lastTxt = range.max != null ? ('第' + chapNo(range.max) + '章最后') : '最后章节未提供';
    var head = '参与 <b>' + fp.lines.length + '</b> 条线 · <b>' + fp.eventCount + '</b> 件事 · ' + esc(firstTxt) + ' · ' + esc(lastTxt);
    var rows = [];
    for (var i = 0; i < fp.lines.length; i++) { rows.push(renderRow(model, fp.lines[i], axis)); }
    return '<section class="atlas-footprint" aria-label="' + esc(name) + ' 的剧情线足迹">' +
      '<header class="af-head">' + head + '</header>' +
      '<ul class="af-lines" role="list">' + rows.join('') + '</ul>' +
      '</section>';
  }

  // ---------------------------------------------------------------- mount
  /** mount(host, {model, character, onLine, onEvent}) → { update(character), dispose() }
   * 一次 mount 只建一个内部包裹节点、只挂一次 click/keydown（事件委托）；
   * update() 只重画包裹节点的 innerHTML，监听器原地复用，不重建——契约 §0「就地换人不重建监听」。
   */
  function mount(host, opts) {
    opts = (opts && typeof opts === 'object') ? opts : {};
    var model = opts.model, character = opts.character, onLine = opts.onLine, onEvent = opts.onEvent;
    var wrap = doc.createElement('div');
    wrap.className = 'atlas-footprint-mount';
    host.appendChild(wrap);

    function paint(ch) { wrap.innerHTML = render(model, ch); }

    function actTarget(e) {
      var t = e.target;
      while (t && t !== wrap) {
        if (t.getAttribute && t.getAttribute('data-act')) { return t; }
        t = t.parentNode;
      }
      return null;
    }
    function fire(t) {
      var act = t.getAttribute('data-act');
      if (act === 'line') {
        var raw = t.getAttribute('data-line-id'), isNumId = t.getAttribute('data-line-id-num') === '1';
        if (typeof onLine === 'function') { onLine(isNumId ? Number(raw) : raw); }
      } else if (act === 'event') {
        var idx = t.getAttribute('data-event-idx');
        if (typeof onEvent === 'function') { onEvent(Number(idx)); }
      }
    }
    function onClick(e) { var t = actTarget(e); if (t) { fire(t); } }
    function onKeydown(e) {
      if (e.key !== 'Enter' && e.key !== ' ' && e.key !== 'Spacebar') { return; }
      var t = actTarget(e);
      if (t && t.getAttribute('data-act') === 'event') {
        if (e.preventDefault) { e.preventDefault(); }
        fire(t);
      }
    }
    wrap.addEventListener('click', onClick);
    wrap.addEventListener('keydown', onKeydown);
    paint(character);

    return {
      update: function (ch) { character = ch; paint(character); },
      dispose: function () {
        wrap.removeEventListener('click', onClick);
        wrap.removeEventListener('keydown', onKeydown);
        if (wrap.parentNode) { wrap.parentNode.removeChild(wrap); }
      }
    };
  }

  g.CLAtlasFootprint = { mount: mount, render: render, VERSION: VERSION };
})(typeof window !== 'undefined' ? window : this);
