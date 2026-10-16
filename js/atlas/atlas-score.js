(function () {
  'use strict';

  var VERSION = '7.0';
  var MINCOL = 30;
  var CHAP_BUCKET = 60;
  var MAX_FLAT_ROWS = 40;
  var MAX_CHIPS = 5;
  var NARROW_MAX_CHIPS = 2;
  var NARROW_BP = 600;
  var TABLET_BP = 900;
  var AXIS_MAJOR_STEP = 5;
  var AXIS_MAJOR_W = 26;
  var AXIS_MINOR_W = 8;
  var VBH = 32;

  // ---------------------------------------------------------------- 小工具（防御式访问，不推断）
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function num(v) { return typeof v === 'number' && isFinite(v) ? v : null; }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function idEq(a, b) { return a != null && b != null && a === b; }
  function byId(list, id) {
    var i;
    for (i = 0; i < list.length; i++) { if (idEq(list[i] && list[i].id, id)) return list[i]; }
    return null;
  }

  // ---------------------------------------------------------------- 章轴（x = 叙事顺序）
  function buildAxis(model) {
    var chapters = arr(model && model.chapters), n = chapters.length, cols = [], i, b, from, to, bucketSize;
    if (!n) { cols.push({ from: 0, to: 0, label: '—' }); return cols; }
    if (n <= CHAP_BUCKET) {
      for (i = 0; i < n; i++) {
        var c = chapters[i] || {}, idx = num(c.idx) != null ? c.idx : i;
        cols.push({ from: idx, to: idx, label: c.name ? esc(c.name) : ('第' + (idx + 1) + '章') });
      }
    } else {
      bucketSize = Math.ceil(n / CHAP_BUCKET);
      for (b = 0; b * bucketSize < n; b++) {
        from = b * bucketSize; to = Math.min(n - 1, from + bucketSize - 1);
        var names = [];
        for (var k = from; k <= to; k++) {
          var cc = chapters[k] || {}, cidx = num(cc.idx) != null ? cc.idx : k;
          names.push(cc.name ? String(cc.name) : ('第' + (cidx + 1) + '章'));
        }
        cols.push({ from: from, to: to, label: '第' + (from + 1) + '–' + (to + 1) + '章', names: names });
      }
    }
    return cols;
  }
  function chapToCol(cols, chapIdx) {
    var i;
    if (chapIdx == null) return -1;
    for (i = 0; i < cols.length; i++) { if (chapIdx >= cols[i].from && chapIdx <= cols[i].to) return i; }
    return chapIdx < cols[0].from ? 0 : cols.length - 1;
  }

  // ---------------------------------------------------------------- 事件索引（按 model.events 下标对齐，契约 §1）
  function buildEventIndex(model) {
    var events = arr(model && model.events), map = {}, i, e, k;
    for (i = 0; i < events.length; i++) {
      e = events[i]; if (!e || typeof e !== 'object') continue;
      k = num(e.i); if (k == null) k = i;
      map[k] = e;
    }
    return map;
  }

  // ---------------------------------------------------------------- 行文案（契约 R2 双长度 / 未命名 / lead）
  function lengthDetail(line) {
    var m = num(line.eventCount);
    if (m == null) m = arr(line.eventIdxs).length;
    var span = line.span || {};
    if (span.known) {
      var n = num(span.chapCount);
      if (n == null && num(span.startChap) != null && num(span.endChap) != null) n = span.endChap - span.startChap + 1;
      var text = '跨 ' + (n == null ? '—' : n) + ' 章 · ' + m + ' 事';
      var touched = num(span.chapTouched);
      var extra = (touched != null && n != null && touched < n) ? ('涉 ' + touched + ' 章') : null;
      return { text: text, extra: extra };
    }
    return { text: m + ' 事 · 章跨未提供', extra: null };
  }
  function lengthText(line) { return lengthDetail(line).text; }
  function chapNameFor(model, chapIdx) {
    if (chapIdx == null) return null;
    var chapters = arr(model && model.chapters), i;
    for (i = 0; i < chapters.length; i++) {
      var c = chapters[i] || {}, cidx = num(c.idx) != null ? c.idx : i;
      if (cidx === chapIdx) return c.name ? String(c.name) : null;
    }
    return null;
  }
  function spanRangeText(line, model) {
    var span = line.span || {};
    if (!span.known || num(span.startChap) == null || num(span.endChap) == null) return null;
    var sName = chapNameFor(model, span.startChap), eName = chapNameFor(model, span.endChap);
    var s = '第 ' + (span.startChap + 1) + ' 章' + (sName ? ' ' + sName : '');
    var e = '第 ' + (span.endChap + 1) + ' 章' + (eName ? ' ' + eName : '');
    return span.startChap === span.endChap ? s : (s + ' → ' + e);
  }
  function leadText(line) {
    var lead = line.lead || {};
    if (lead.known && lead.name) return esc(lead.name);
    return '领衔未定';
  }
  function nameText(line, unnamedIdx) {
    if (line.nameKnown === false) return '未命名线 · 第 ' + unnamedIdx + '';
    return esc(line.name || '');
  }
  var STATUS_GLYPH = { resolved: 'end-resolved', suspended: 'end-suspended', open: 'end-open', conflict: 'end-unknown', unknown: 'end-unknown' };
  var STATUS_LABEL = { resolved: '收束', suspended: '悬置', open: '进行中', conflict: '状态冲突', unknown: '状态未提供' };
  function statusInfo(line) {
    var known = line.statusKnown !== false && !!line.status && line.status !== 'unknown';
    var st = known ? line.status : 'unknown';
    return { glyphKind: STATUS_GLYPH[st] || 'end-unknown', label: STATUS_LABEL[st] || '状态未提供', known: known, raw: st };
  }

  // ---------------------------------------------------------------- 自绘极简符号（行内 SVG 坐标系专用）
  function capShape(kind, x, y, r, cls) {
    switch (kind) {
      case 'start':
        return '<circle class="cl-score-glyph cl-score-cap-start ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-resolved':
        return '<circle class="cl-score-glyph cl-score-cap-end is-resolved ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-suspended':
        return '<circle class="cl-score-glyph cl-score-cap-end is-suspended ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-open':
        return '<circle class="cl-score-glyph cl-score-cap-end is-open ' + cls + '" cx="' + x + '" cy="' + y + '" r="' + r + '"/>';
      case 'end-unknown':
      default:
        return '<g class="cl-score-glyph cl-score-cap-end is-unknown ' + cls + '">' +
          '<circle cx="' + x + '" cy="' + y + '" r="' + r + '"/>' +
          '<text x="' + x + '" y="' + (y + 1) + '" text-anchor="middle" dominant-baseline="middle">?</text></g>';
    }
  }
  function turnShape(x, y, kind) {
    var r = 3;
    return '<path class="cl-score-glyph cl-score-turn" data-turn-kind="' + esc(kind) + '"' +
      ' d="M ' + x + ' ' + (y - r) + ' L ' + (x + r) + ' ' + y + ' L ' + x + ' ' + (y + r) + ' L ' + (x - r) + ' ' + y + ' Z">' +
      '<title>' + esc(kind) + '</title></path>';
  }
  function handoffShape(x, top, bottom, known, tipText) {
    var midY = (top + bottom) / 2;
    var text = tipText || '';
    var tipW = Math.max(64, text.length * 11 + 14);
    return '<g class="cl-score-glyph cl-score-handoff ' + (known ? 'is-known' : 'is-unknown') + '" data-x="' + x + '" tabindex="0" role="img" aria-label="' + esc(text) + '">' +
      '<line x1="' + x + '" y1="' + top + '" x2="' + x + '" y2="' + bottom + '"/>' +
      '<circle cx="' + x + '" cy="' + top + '" r="2.4"/>' +
      '<title>' + esc(text) + '</title>' +
      '<g class="cl-score-handoff-tip" transform="translate(' + x + ',' + midY + ')">' +
        '<rect class="cl-score-handoff-tip-bg" x="4" y="-8" width="' + tipW + '" height="16" rx="2"></rect>' +
        '<text class="cl-score-handoff-tip-text" x="10" y="3">' + esc(text) + '</text>' +
      '</g>' +
    '</g>';
  }
  function forkPath(xAttach, xStart, h) {
    var midY = h * 0.55;
    return '<path class="cl-score-glyph cl-score-fork" d="M ' + xAttach + ' 0 C ' + xAttach + ' ' + (h * 0.35) +
      ' ' + xStart + ' ' + (h * 0.2) + ' ' + xStart + ' ' + midY + '"/>';
  }

  // ---------------------------------------------------------------- R5-M ①：主线更替说明条（代次分组头之间）
  function lineDisplayName(line) {
    if (!line) return null;
    if (line.nameKnown === false) return '未命名线';
    return line.name || String(line.id);
  }
  function successionInfo(fromLine, toLine, evIdx) {
    var ho = toLine && toLine.handoff;
    var known = !!(ho && ho.known && fromLine && idEq(ho.fromId, fromLine.id));
    var fromName = lineDisplayName(fromLine) || '主线未知';
    var toName = lineDisplayName(toLine) || '主线未知';
    if (!known) return { text: fromName + ' → ' + toName + ' · 更替依据未提供', known: false };
    var atEv = ho.atEventIdx != null ? evIdx[num(ho.atEventIdx)] : null;
    var chapLabel = atEv && num(atEv.chapIdx) != null ? ('第 ' + (atEv.chapIdx + 1) + ' 章')
      : (atEv && atEv.chapName ? atEv.chapName : '章节未提供');
    var evTitle = atEv && atEv.title ? atEv.title : '触发事件名未提供';
    return {
      text: chapLabel + ' · ' + fromName + ' → ' + toName + ' · ' + evTitle,
      known: true,
      reason: ho.reason || null
    };
  }
  function successionGlyph() {
    try {
      if (window.CLAtlasGlyphs && typeof window.CLAtlasGlyphs.use === 'function') {
        return window.CLAtlasGlyphs.use('handoff', 'cl-score-succession-glyph');
      }
    } catch (eG) {}
    return '<svg class="cl-score-succession-glyph is-fallback" viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">' +
      '<line x1="3" y1="11" x2="11" y2="3"/><circle cx="11" cy="3" r="2.2"/></svg>';
  }
  function successionBannerHtml(fromLine, toLine, evIdx, fromGen, toGen) {
    var info = successionInfo(fromLine, toLine, evIdx);
    var ariaLabel = info.text + (info.reason ? (' · ' + info.reason) : '');
    return '<div class="cl-score-succession' + (info.known ? ' is-known' : ' is-unknown') + '" role="note"' +
      ' data-from-gen="' + esc(fromGen) + '" data-to-gen="' + esc(toGen) + '" tabindex="0" aria-label="' + esc(ariaLabel) + '">' +
      successionGlyph() +
      '<span class="cl-score-succession-text">' + esc(info.text) + '</span>' +
      (info.reason ? ('<span class="cl-score-succession-reason">' + esc(info.reason) + '</span>') : '') +
    '</div>';
  }
  function findMainInGroup(group) {
    var i, lines2 = group.lines;
    for (i = 0; i < lines2.length; i++) { if (lines2[i] && lines2[i].kind === 'main') return lines2[i]; }
    return null;
  }
  function currentActiveMainGen(lines) {
    var fromIds = {}, knownLinks = 0, i, ln, ho;
    for (i = 0; i < lines.length; i++) {
      ln = lines[i]; ho = ln && ln.handoff;
      if (ln && ln.kind === 'main' && ho && ho.known && ho.fromId != null) { knownLinks++; fromIds[ho.fromId] = 1; }
    }
    if (knownLinks < 2) return null;
    var tails = [];
    for (i = 0; i < lines.length; i++) {
      ln = lines[i]; ho = ln && ln.handoff;
      if (ln && ln.kind === 'main' && ho && ho.known && ln.id != null && !fromIds[ln.id]) tails.push(ln);
    }
    if (!tails.length) return null;
    var openTails = [];
    for (i = 0; i < tails.length; i++) {
      if (tails[i].statusKnown !== false && tails[i].status === 'open') openTails.push(tails[i]);
    }
    var pool = openTails.length ? openTails : tails;
    var best = pool[0];
    for (i = 1; i < pool.length; i++) {
      var a = pool[i];
      var ae = num(a.span && a.span.endChap), be = num(best.span && best.span.endChap);
      var aKey = ae != null ? ae : (typeof a.gen === 'number' ? a.gen : -Infinity);
      var bKey = be != null ? be : (typeof best.gen === 'number' ? best.gen : -Infinity);
      if (aKey > bKey) best = a;
    }
    return best.gen == null ? '␀' : best.gen;
  }

  // ---------------------------------------------------------------- 分组 / 排序（脊在前，支线按挂点跟随）
  function groupByGen(lines) {
    var buckets = {}, order = [], i, ln, g;
    for (i = 0; i < lines.length; i++) {
      ln = lines[i]; g = ln.gen == null ? '␀' : ln.gen;
      if (!buckets[g]) { buckets[g] = []; order.push(g); }
      buckets[g].push(ln);
    }
    order.sort(function (a, b) {
      if (a === '␀') return 1; if (b === '␀') return -1; return a - b;
    });
    return order.map(function (g) { return { gen: g, lines: buckets[g] }; });
  }
  function sortRows(lines) {
    return lines.slice().sort(function (a, b) {
      var ka = a.kind === 'main' ? 0 : (a.kind === 'branch' ? 1 : 2);
      var kb = b.kind === 'main' ? 0 : (b.kind === 'branch' ? 1 : 2);
      if (ka !== kb) return ka - kb;
      var an = num(a.attachEventIdx), bn = num(b.attachEventIdx);
      an = an == null ? Infinity : an; bn = bn == null ? Infinity : bn;
      if (an !== bn) return an - bn;
      return 0;
    });
  }

  // ---------------------------------------------------------------- 参与者三级（契约 R4：lead/core ≤5 + N 展开）
  function castChips(line, maxChips) {
    maxChips = maxChips || MAX_CHIPS;
    var cast = arr(line.cast);
    var lead = [], core = [], minor = [];
    var i, c;
    for (i = 0; i < cast.length; i++) {
      c = cast[i]; if (!c) continue;
      if (c.role === 'lead') lead.push(c); else if (c.role === 'core') core.push(c); else minor.push(c);
    }
    var visible = lead.concat(core).slice(0, maxChips);
    var seen = {}, j;
    for (j = 0; j < visible.length; j++) seen[visible[j].name] = 1;
    var rest = [];
    for (i = 0; i < cast.length; i++) { c = cast[i]; if (c && !seen[c.name]) rest.push(c); }
    return { visible: visible, rest: rest, total: cast.length };
  }
  function chipGlyph(role) {
    try {
      if (window.CLAtlasGlyphs && typeof window.CLAtlasGlyphs.use === 'function') {
        return window.CLAtlasGlyphs.use(role, 'cl-score-chip-glyph');
      }
    } catch (eG) {}
    if (role === 'lead') return '<svg class="cl-score-chip-glyph is-fallback" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="4"/></svg>';
    if (role === 'core') return '<svg class="cl-score-chip-glyph is-fallback" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="3"/></svg>';
    return '<svg class="cl-score-chip-glyph is-fallback" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true"><circle cx="5" cy="5" r="2.2" fill="none"/></svg>';
  }
  function chipHtml(c, extraCls) {
    var role = c.role || 'minor';
    return '<button type="button" class="cl-score-chip cl-score-chip-' + esc(role) + (extraCls ? ' ' + extraCls : '') +
      '" data-role="' + esc(role) + '" data-character="' + esc(c.name) + '" aria-pressed="false" title="' + esc(({ lead: '主导', core: '常驻', minor: '客串' })[role] || '参与') + (num(c.events) != null ? ' · ' + c.events + '事' : '') + ' · 点击查看跨线足迹">' + chipGlyph(role) + '<span class="cl-score-chip-name">' + esc(c.name) + '</span></button>';
  }

  // ---------------------------------------------------------------- 列几何（R5-M：均匀列宽 / 两级刻度变宽列 统一走同一套读法）
  function makeGeom(cols, colW) {
    var n = cols.length, x = new Array(n), i;
    for (i = 0; i < n; i++) x[i] = i * colW;
    return { x: x, w: function () { return colW; }, total: Math.max(colW, n * colW) };
  }
  function makeVarGeom(cols, widths) {
    var n = cols.length, x = new Array(n), i, acc = 0;
    for (i = 0; i < n; i++) { x[i] = acc; acc += widths[i]; }
    return { x: x, w: function (i2) { return widths[i2]; }, total: acc };
  }
  // ---------------------------------------------------------------- 事件在章轴上的 x（同章多事件在列内均分）
  function chapPositions(cols, geom, eventIdxsSortedByChap) {
    var byChap = {}, i, e;
    for (i = 0; i < eventIdxsSortedByChap.length; i++) {
      e = eventIdxsSortedByChap[i];
      var col = chapToCol(cols, e.chapIdx);
      if (!byChap[col]) byChap[col] = [];
      byChap[col].push(i);
    }
    var xs = new Array(eventIdxsSortedByChap.length);
    Object.keys(byChap).forEach(function (colKey) {
      var col = +colKey, list = byChap[colKey], n = list.length, k, w = geom.w(col);
      for (k = 0; k < n; k++) {
        xs[list[k]] = geom.x[col] + w * ((k + 0.5) / n);
      }
    });
    for (i = 0; i < xs.length; i++) { if (xs[i] == null) xs[i] = 0; }
    return xs;
  }

  // ---------------------------------------------------------------- R7-F：未归线事件轨
  function orphanEvents(model) {
    var events = arr(model && model.events), idxs = [], placed = 0, i, e;
    for (i = 0; i < events.length; i++) {
      e = events[i]; if (!e || typeof e !== 'object') continue;
      if (arr(e.lineIds).length > 0) placed++;
      else { var k = num(e.i); idxs.push(k == null ? i : k); }
    }
    return { idxs: idxs, placed: placed, total: placed + idxs.length };
  }
  function buildOrphanTrack(idxs, cols, geom, evIdx) {
    var totalW = geom.total, rowH = VBH, midY = rowH * 0.5, i, ei, e;
    var chapOf = [];
    for (i = 0; i < idxs.length; i++) {
      ei = idxs[i]; e = evIdx[ei] || null;
      chapOf.push({ i: ei, chapIdx: e ? num(e.chapIdx) : null, title: e ? e.title : null, order: e ? num(e.order) : null });
    }
    chapOf.sort(function (a, b) { var oa = a.order == null ? 0 : a.order, ob = b.order == null ? 0 : b.order; return oa - ob; });
    var xs = chapPositions(cols, geom, chapOf);
    var html = '<svg class="cl-score-svg cl-score-orphan-svg" data-role="orphan-track" viewBox="0 0 ' + totalW + ' ' + rowH + '" preserveAspectRatio="none" width="' + totalW + '" height="' + rowH + '">';
    html += '<line class="cl-score-orphan-baseline" x1="0" y1="' + midY + '" x2="' + totalW + '" y2="' + midY + '"/>';
    for (i = 0; i < chapOf.length; i++) {
      var x = xs[i];
      html += '<line class="cl-score-tick cl-score-orphan-tick" data-orphan="1" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="' + (midY - 5) + '" x2="' + x + '" y2="' + (midY + 5) + '">' +
        (chapOf[i].title ? '<title>' + esc(chapOf[i].title) + '</title>' : '') + '</line>';
      html += '<line class="cl-score-tick-hit" data-orphan="1" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="0" x2="' + x + '" y2="' + rowH + '"/>';
    }
    html += '</svg>';
    return html;
  }
  function orphanSectionHtml(model, cols, geom, evIdx, orph) {
    var n = orph.idxs.length;
    if (!n) return '';
    var coveragePct = orph.total > 0 ? Math.round(orph.placed / orph.total * 100) : 0;
    var headText = '未归线 ' + n + ' 事 · 覆盖 ' + coveragePct + '%';
    return (
      '<section class="cl-score-orphan" role="rowgroup" data-orphans="' + n + '" data-coverage="' + coveragePct + '" aria-label="' + esc(headText + '（归线事件占比 ' + orph.placed + '/' + orph.total + '）') + '">' +
        '<div class="cl-score-orphan-row" data-orphan-row="1">' +
          '<div class="cl-score-orphan-rowhead" tabindex="0" title="' + esc('归线事件占比 ' + orph.placed + '/' + orph.total) + '">' +
            '<span class="cl-score-orphan-name">' + esc(headText) + '</span>' +
          '</div>' +
          '<div class="cl-score-orphan-track">' + buildOrphanTrack(orph.idxs, cols, geom, evIdx) + '</div>' +
        '</div>' +
      '</section>'
    );
  }

  // ---------------------------------------------------------------- 一行的 track SVG（事件刻度批量 + 转折 + 帽 + 分叉 + 接头）
  function buildTrack(line, cols, geom, evIdx, linesById) {
    var totalW = geom.total;
    var eventIdxs = arr(line.eventIdxs);
    var chapOf = [], i, ei, e, minChap = null, maxChap = null;
    for (i = 0; i < eventIdxs.length; i++) {
      ei = num(eventIdxs[i]); e = ei != null ? evIdx[ei] : null;
      var chapIdx = e ? num(e.chapIdx) : null;
      chapOf.push({ i: ei, chapIdx: chapIdx, title: e ? e.title : null, order: e ? num(e.order) : null });
      if (chapIdx != null) { minChap = minChap == null ? chapIdx : Math.min(minChap, chapIdx); maxChap = maxChap == null ? chapIdx : Math.max(maxChap, chapIdx); }
    }
    chapOf.sort(function (a, b) { var oa = a.order == null ? 0 : a.order, ob = b.order == null ? 0 : b.order; return oa - ob; });
    var xs = chapPositions(cols, geom, chapOf);
    var rowH = VBH, barY = line.kind === 'main' ? rowH * 0.42 : (line.kind === 'branch' ? rowH * 0.46 : rowH * 0.5);
    var barH = line.kind === 'main' ? 10 : (line.kind === 'branch' ? 6 : 4);
    var genCls = 'gen-' + (line.gen == null ? 'x' : line.gen);
    var barCls = 'cl-score-bar-' + line.kind + ' ' + genCls;
    var span = line.span || {}, spanUnknown = !span.known;
    var startChap = (!spanUnknown && num(span.startChap) != null) ? span.startChap : minChap;
    var endChap = (!spanUnknown && num(span.endChap) != null) ? span.endChap : maxChap;
    var barX, barW;
    if (startChap != null && endChap != null) {
      var c0 = chapToCol(cols, startChap), c1 = chapToCol(cols, endChap);
      var w0 = geom.w(c0), w1 = geom.w(c1);
      barX = geom.x[c0] + w0 * 0.08;
      barW = Math.max(w0 * 0.5, (geom.x[c1] + w1) - geom.x[c0] - w0 * 0.08 - w1 * 0.08);
    } else {
      var w00 = geom.w(0);
      barX = w00 * 0.08; barW = Math.max(w00 * 0.5, totalW - w00 * 0.16);
    }
    var html = '<svg class="cl-score-svg" data-role="track" viewBox="0 0 ' + totalW + ' ' + rowH + '" preserveAspectRatio="none" width="' + totalW + '" height="' + rowH + '">';
    if ((line.kind === 'branch' || line.kind === 'twig') && num(line.attachEventIdx) != null) {
      var ae = evIdx[num(line.attachEventIdx)];
      var attachChap = ae ? num(ae.chapIdx) : null;
      var attachCol = attachChap != null ? chapToCol(cols, attachChap) : null;
      var attachX = attachCol != null ? (geom.x[attachCol] + geom.w(attachCol) * 0.5) : barX;
      html += forkPath(attachX, barX, rowH);
    }
    html += '<rect class="cl-score-bar ' + barCls + (spanUnknown ? ' is-span-unknown' : '') + '" x="' + barX + '" y="' + barY + '" width="' + barW + '" height="' + barH + '" rx="' + (barH / 2) + '"/>';
    var midY = barY + barH / 2;
    html += capShape('start', barX, midY, barH * 0.62, 'cl-score-cap-r-' + line.kind);
    var st = statusInfo(line);
    html += capShape(st.glyphKind, barX + barW, midY, barH * 0.62, 'cl-score-cap-r-' + line.kind);
    var turns = arr(line.turns), turnByIdx = {};
    for (i = 0; i < turns.length; i++) { var t = turns[i]; if (t && num(t.eventIdx) != null) turnByIdx[t.eventIdx] = t.kind; }
    var tickLines = '';
    for (i = 0; i < chapOf.length; i++) {
      var x = xs[i];
      tickLines += '<line class="cl-score-tick" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="' + (barY - 3) + '" x2="' + x + '" y2="' + (barY + barH + 3) + '">' +
        (chapOf[i].title ? '<title>' + esc(chapOf[i].title) + '</title>' : '') + '</line>';
      if (chapOf[i].i != null && turnByIdx.hasOwnProperty(chapOf[i].i)) {
        tickLines += turnShape(x, barY - 6, turnByIdx[chapOf[i].i]);
      }
      tickLines += '<line class="cl-score-tick-hit" data-event-idx="' + chapOf[i].i + '" x1="' + x + '" y1="0" x2="' + x + '" y2="' + rowH + '"/>';
    }
    html += tickLines;
    if (line.kind === 'main' && line.gen != null && line.gen > 0) {
      var ho = line.handoff || null, hoKnown = !!(ho && ho.known);
      var hxCol = (ho && num(ho.atEventIdx) != null && evIdx[num(ho.atEventIdx)] && num(evIdx[num(ho.atEventIdx)].chapIdx) != null)
        ? chapToCol(cols, evIdx[num(ho.atEventIdx)].chapIdx) : null;
      var hx = hxCol != null ? (geom.x[hxCol] + geom.w(hxCol) * 0.5) : barX;
      var tipText;
      if (hoKnown) {
        var fromLine = linesById && ho.fromId != null ? linesById[ho.fromId] : null;
        var fromName = fromLine ? (fromLine.nameKnown === false ? '未命名线' : (fromLine.name || String(fromLine.id))) : '让位者未知';
        var toName = line.nameKnown === false ? '未命名线' : (line.name || String(line.id));
        var atEv = num(ho.atEventIdx) != null ? evIdx[num(ho.atEventIdx)] : null;
        var chapLabel = atEv && atEv.chapName ? atEv.chapName : (atEv && num(atEv.chapIdx) != null ? ('第 ' + (atEv.chapIdx + 1) + ' 章') : '章节未提供');
        var reasonText = ho.reason ? ho.reason : '理由未提供';
        tipText = fromName + ' → ' + toName + ' · ' + chapLabel + ' · ' + reasonText;
      } else {
        tipText = '更替依据未提供';
      }
      html += handoffShape(hx, 2, rowH - 2, hoKnown, tipText);
    }
    return { html: html, barX: barX, barTailX: barX + barW, rowH: rowH, totalW: totalW };
  }
  function renderTrack(line, cols, geom, evIdx, linesById) {
    var t = buildTrack(line, cols, geom, evIdx, linesById);
    return t.html + '</svg>';
  }

  // ---------------------------------------------------------------- 一行整体（行头 + track + 参与者带）
  // ---------------------------------------------------------------- 参与者带（独立行 / 内嵌 foreignObject 两种落地方式）
  function castButtons(line, maxChips, skipInlineRest) {
    var chips = castChips(line, maxChips);
    var visibleHtml = chips.visible.map(function (c) { return chipHtml(c, ''); }).join('');
    var restHtml = skipInlineRest ? '' : chips.rest.map(function (c) { return chipHtml(c, 'is-extra'); }).join('');
    var moreBtn = chips.rest.length
      ? '<button type="button" class="cl-score-chip cl-score-chip-more" data-more="1" aria-expanded="false">+' + chips.rest.length + '</button>' : '';
    return { chips: chips, html: visibleHtml + restHtml + moreBtn };
  }
  function castStandaloneHtml(line, maxChips) {
    var narrow = !!maxChips && maxChips < MAX_CHIPS;
    var c = castButtons(line, maxChips, narrow);
    var html = '<div class="cl-score-cast' + (narrow ? ' cl-score-cast-narrow' : '') + '" data-line-id="' + esc(line.id) + '">' + c.html + '</div>';
    if (narrow && c.chips.rest.length) {
      var moreHtml = c.chips.rest.map(function (r) { return chipHtml(r, ''); }).join('');
      html += '<div class="cl-score-cast-more" data-line-id="' + esc(line.id) + '" hidden>' + moreHtml + '</div>';
    }
    return html;
  }
  function castForeignObjectHtml(line, x, w, rowH, maxChips) {
    var c = castButtons(line, maxChips);
    return '<foreignObject x="' + x + '" y="0" width="' + Math.max(40, w) + '" height="' + rowH + '">' +
      '<div xmlns="http://www.w3.org/1999/xhtml" class="cl-score-cast cl-score-cast-inline" data-line-id="' + esc(line.id) + '">' + c.html + '</div>' +
    '</foreignObject>';
  }

  // ---------------------------------------------------------------- 一行整体（行头 + track + 参与者带）
  function renderRow(line, cols, geom, evIdx, unnamedIdx, inline, linesById, maxChips, model) {
    var st = statusInfo(line);
    var lenDetail = lengthDetail(line);
    var rangeTxt = spanRangeText(line, model);
    var ariaLabel = nameText(line, unnamedIdx) + '（' + leadText(line) + '）· ' + lenDetail.text +
      (lenDetail.extra ? (' · ' + lenDetail.extra) : '') + (rangeTxt ? (' · ' + rangeTxt) : '') +
      ' · ' + st.label + ' · ' + castChips(line).total + ' 人参与';
    var rowCls = 'cl-score-row is-' + line.kind + (line.gen == null ? ' is-gen-unknown' : '');
    var t = buildTrack(line, cols, geom, evIdx, linesById);
    var trackInner = t.html;
    if (inline) {
      trackInner += castForeignObjectHtml(line, t.barTailX + 8, t.totalW - t.barTailX - 16, t.rowH, maxChips);
    }
    trackInner += '</svg>';
    if (!inline) trackInner += castStandaloneHtml(line, maxChips);
    return (
      '<div class="' + rowCls + '" role="row" tabindex="-1" data-line-id="' + esc(line.id) + '" data-kind="' + esc(line.kind) + '" data-gen="' + (line.gen == null ? '' : esc(line.gen)) + '" aria-label="' + esc(ariaLabel) + '">' +
        '<div class="cl-score-rowhead" data-line-id="' + esc(line.id) + '">' +
          '<span class="cl-score-rowcap" title="' + esc(st.label) + '">' +
            '<svg class="cl-score-mini" viewBox="0 0 10 10" width="10" height="10" aria-hidden="true">' + capShape(st.glyphKind, 5, 5, 3.4, 'cl-score-mini-' + st.raw) + '</svg>' +
          '</span>' +
          '<span class="cl-score-name">' + nameText(line, unnamedIdx) + '</span>' +
          '<span class="cl-score-subline"' + (lenDetail.extra ? (' title="' + esc(lenDetail.extra) + '"') : '') + '>' +
            '<span class="cl-score-status is-' + esc(st.raw) + '">' + esc(st.label) + '</span>' +
            '<span class="cl-score-lead">' + leadText(line) + '</span>' +
            '<span class="cl-score-len">' + esc(lenDetail.text) + '</span>' +
            (rangeTxt ? ('<span class="cl-score-span-range" title="' + esc(rangeTxt) + '">' + esc(rangeTxt) + '</span>') : '') +
            '<span class="cl-score-len-compact" title="' + esc(lenDetail.text) + '">' + esc(lenDetail.text.replace(/ /g, '')) + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="cl-score-track' + (inline ? ' is-cast-inline' : '') + '" data-line-id="' + esc(line.id) + '">' + trackInner + '</div>' +
      '</div>'
    );
  }

  // ---------------------------------------------------------------- 章轴（sticky top，自动稀疏文字标签）
  function estimateLabelWidth(label) { return (label ? String(label).length : 1) * 13; }
  function computeAxisStep(cols, colW) {
    if (cols.length <= 12) return 1;
    var maxW = 0, i, w;
    for (i = 0; i < cols.length; i++) { w = estimateLabelWidth(cols[i].label); if (w > maxW) maxW = w; }
    var required = maxW + 8;
    return Math.max(1, Math.ceil(required / colW));
  }
  function bucketTipText(col) {
    var names = col.names;
    if (!names || !names.length) return null;
    return col.label + '：' + names.join('、');
  }
  function buildAxisSvgHtml(cols, geom, majorMask) {
    var totalW = geom.total, i, html = '';
    var k = majorMask ? 1 : computeAxisStep(cols, geom.w(0)), lastShown = -Infinity;
    for (i = 0; i < cols.length; i++) {
      var isMajor = majorMask ? majorMask[i] : null;
      var showText = majorMask ? isMajor : (i % k === 0);
      if (!majorMask && !showText && i === cols.length - 1 && (i - lastShown) * geom.w(0) >= (estimateLabelWidth(cols[i].label) + 8)) showText = true;
      if (showText) lastShown = i;
      var isBucket = !!(cols[i].names && cols[i].names.length);
      var tip = isBucket ? bucketTipText(cols[i]) : null;
      var x0 = geom.x[i], w = geom.w(i);
      var label = majorMask ? String(cols[i].from + 1) : cols[i].label;
      var tickY2 = majorMask ? (isMajor ? 18 : 11) : 18;
      html += '<g class="cl-score-axis-col' + (showText ? '' : ' is-tick-only') + (isBucket ? ' is-bucket' : '') +
        (majorMask ? (isMajor ? ' is-axis-major' : ' is-axis-minor') : '') + '" data-col="' + i + '"' +
        (isBucket ? (' tabindex="0" role="img" aria-label="' + esc(tip) + '"') : '') + '>' +
        '<line x1="' + x0 + '" y1="0" x2="' + x0 + '" y2="' + tickY2 + '"/>' +
        (isBucket ? ('<title>' + esc(tip) + '</title>') : '') +
        (showText ? ('<text x="' + (x0 + w / 2) + '" y="13" text-anchor="middle">' + label + '</text>') : '') +
      '</g>';
    }
    return '<svg class="cl-score-axis-svg" viewBox="0 0 ' + totalW + ' 18" preserveAspectRatio="none" width="' + totalW + '" height="18">' + html + '</svg>';
  }
  function renderAxis(cols, geom) {
    return (
      '<div class="cl-score-axis">' +
        '<div class="cl-score-axis-spacer" aria-hidden="true"></div>' +
        buildAxisSvgHtml(cols, geom) +
      '</div>'
    );
  }

  // ---------------------------------------------------------------- 事件卡（契约补充：点刻度必须有可见元素）
  function eventCardShell() {
    return (
      '<div class="cl-score-eventcard is-hidden" role="dialog" aria-modal="false" aria-labelledby="cl-score-card-title" aria-live="polite">' +
        '<button type="button" class="cl-score-eventcard-close" data-eventcard-close="1" aria-label="关闭事件卡">×</button>' +
        '<div class="cl-score-eventcard-body"></div>' +
      '</div>'
    );
  }
  function chapterLabel(e) {
    if (!e) return '章节未提供';
    if (e.chapName) return esc(e.chapName);
    if (num(e.chapIdx) != null) return '第 ' + (e.chapIdx + 1) + ' 章';
    return '章节未提供';
  }
  function castRoleRankForEvent(e, model) {
    var ranks = {};
    if (e && Array.isArray(e.lineIds) && model) {
      var lines = arr(model.lines), li3, ci3, k3, ln3, cast3, c3, rank3;
      for (li3 = 0; li3 < e.lineIds.length; li3++) {
        ln3 = null;
        for (k3 = 0; k3 < lines.length; k3++) { if (idEq(lines[k3].id, e.lineIds[li3])) { ln3 = lines[k3]; break; } }
        if (!ln3) continue;
        cast3 = arr(ln3.cast);
        for (ci3 = 0; ci3 < cast3.length; ci3++) {
          c3 = cast3[ci3]; if (!c3 || !c3.name) continue;
          rank3 = c3.role === 'lead' ? 2 : (c3.role === 'core' ? 1 : 0);
          if (!ranks.hasOwnProperty(c3.name) || rank3 > ranks[c3.name]) ranks[c3.name] = rank3;
        }
      }
    }
    return ranks;
  }
  function rankToRole(r) { return r === 2 ? 'lead' : (r === 1 ? 'core' : 'minor'); }
  function ownerLinesHtml(e, model) {
    if (!e || !model || !Array.isArray(e.lineIds)) {
      return '<span class="cl-score-card-empty">所属线未提供</span>';
    }
    if (!e.lineIds.length) {
      return '<span class="cl-score-card-empty cl-score-card-orphan">未归线</span>';
    }
    var lines = arr(model.lines), out = [], li4, k4, ln4;
    for (li4 = 0; li4 < e.lineIds.length; li4++) {
      ln4 = null;
      for (k4 = 0; k4 < lines.length; k4++) { if (idEq(lines[k4].id, e.lineIds[li4])) { ln4 = lines[k4]; break; } }
      if (!ln4) continue;
      var genCls = 'gen-' + (ln4.gen == null ? 'x' : ln4.gen);
      var nm4 = ln4.nameKnown === false ? '未命名线' : esc(ln4.name || String(ln4.id));
      out.push('<span class="cl-score-card-line" data-line-id="' + esc(ln4.id) + '">' +
        '<span class="cl-score-card-linebar cl-score-bar-' + esc(ln4.kind || 'main') + ' ' + genCls + '"></span>' + nm4 + '</span>');
    }
    return out.length ? out.join('') : '<span class="cl-score-card-empty">所属线未提供</span>';
  }
  function eventCardBodyHtml(e, model) {
    if (!e) return '<p class="cl-score-card-empty">事件未提供</p>';
    var ranks = castRoleRankForEvent(e, model);
    var cast = arr(e.cast);
    var castHtml = cast.length
      ? cast.map(function (nm) { return chipHtml({ name: nm, role: rankToRole(ranks.hasOwnProperty(nm) ? ranks[nm] : 0) }, 'cl-score-card-chip'); }).join('')
      : '<span class="cl-score-card-empty">参与者未提供</span>';
    var quoteHtml = '';
    if (e.quote) {
      quoteHtml = '<figure class="cl-score-card-quote" data-quote-state="collapsed">' +
        '<blockquote class="cl-score-card-quote-text">' + esc(e.quote) + '</blockquote>' +
        '<button type="button" class="cl-score-card-quote-toggle" data-quote-toggle="1" hidden>展开</button>' +
      '</figure>';
    }
    return (
      '<h3 class="cl-score-card-title" id="cl-score-card-title">' + esc(e.title || '（无标题）') + '</h3>' +
      '<div class="cl-score-card-pills">' +
        '<span class="cl-score-card-pill cl-score-card-pill-chap">' + chapterLabel(e) + '</span>' +
        '<span class="cl-score-card-pill cl-score-card-pill-kind">' + (e.kind ? esc(e.kind) : '类型未提供') + '</span>' +
      '</div>' +
      '<div class="cl-score-card-cast">' + castHtml + '</div>' +
      '<div class="cl-score-card-lines">' + ownerLinesHtml(e, model) + '</div>' +
      quoteHtml +
      '<p class="cl-score-card-summary">' + (e.summary ? esc(e.summary) : '摘要未提供') + '</p>' +
      '<button type="button" class="cl-score-card-locate" data-locate-event="' + esc(e.i) + '">在星盘上看</button>'
    );
  }

  // ---------------------------------------------------------------- 分组 + 未命名编号（渲染 / 惰性展开共用一份）
  function computeGroups(model) {
    var lines = arr(model.lines);
    var groups = groupByGen(lines).map(function (g) { return { gen: g.gen, lines: sortRows(g.lines) }; });
    var unnamedIdx = {}, counter = 0, gi, li;
    for (gi = 0; gi < groups.length; gi++) {
      for (li = 0; li < groups[gi].lines.length; li++) {
        var ln = groups[gi].lines[li];
        if (ln.nameKnown === false) { counter++; unnamedIdx[ln.id] = counter; }
      }
    }
    return { groups: groups, unnamedIdx: unnamedIdx };
  }

  // ---------------------------------------------------------------- v71 W2 · U7：代次总览轨（GEN OVERVIEW RAIL）
  function genEventCount(g) {
    return g.lines.reduce(function (s, ln) {
      var c = num(ln.eventCount); return s + (c == null ? arr(ln.eventIdxs).length : c);
    }, 0);
  }
  function lineSpanChaps(line, evIdx) {
    var span = line.span || {};
    if (span.known && num(span.startChap) != null && num(span.endChap) != null) {
      return { s: span.startChap, e: span.endChap };
    }
    var idxs = arr(line.eventIdxs), mn = null, mx = null, i, ei, e, c;
    for (i = 0; i < idxs.length; i++) {
      ei = num(idxs[i]); e = ei != null ? evIdx[ei] : null; c = e ? num(e.chapIdx) : null;
      if (c == null) continue;
      mn = mn == null ? c : Math.min(mn, c); mx = mx == null ? c : Math.max(mx, c);
    }
    if (mn == null) return null;
    return { s: mn, e: mx };
  }
  function overviewGanttSvg(g, cols, evIdx) {
    var nCols = Math.max(1, cols.length);
    var under = '', mains = '', i, ln, sp;
    for (i = 0; i < g.lines.length; i++) {
      ln = g.lines[i]; if (!ln) continue;
      sp = lineSpanChaps(ln, evIdx);
      if (!sp) continue;
      var c0 = clamp(chapToCol(cols, sp.s), 0, nCols - 1);
      var c1 = clamp(chapToCol(cols, sp.e), 0, nCols - 1);
      var x0 = c0 / nCols * 100, w = Math.max(1.2, (c1 + 1) / nCols * 100 - x0);
      var isMain = ln.kind === 'main';
      var rect = '<rect class="cl-score-ov-span is-' + esc(ln.kind) + ' gen-' + (ln.gen == null ? 'x' : ln.gen) +
        '" x="' + x0 + '" y="' + (isMain ? 3 : (ln.kind === 'branch' ? 5 : 6)) +
        '" width="' + w + '" height="' + (isMain ? 8 : (ln.kind === 'branch' ? 4 : 2.5)) + '"/>';
      if (isMain) mains += rect; else under += rect;
    }
    return '<svg class="cl-score-ov-gantt" viewBox="0 0 100 14" preserveAspectRatio="none" aria-hidden="true">' + under + mains + '</svg>';
  }
  function overviewRailHtml(model, groups, cols, evIdx, activeGen, compact) {
    if (!groups.length) return '';
    var counts = [], total = 0, gi;
    for (gi = 0; gi < groups.length; gi++) { counts.push(genEventCount(groups[gi])); total += counts[gi]; }
    var cells = [];
    for (gi = 0; gi < groups.length; gi++) {
      var g = groups[gi];
      var share = total > 0 ? counts[gi] / total * 100 : 100 / groups.length;
      var shareStr = (Math.round(share * 100) / 100).toFixed(2);
      var grow = Math.max(1, Math.round(share * 10));
      var main = findMainInGroup(g);
      var mainName = main ? lineDisplayName(main) : null;
      var branches = 0, twigs = 0, li9;
      for (li9 = 0; li9 < g.lines.length; li9++) {
        if (g.lines[li9].kind === 'branch') branches++;
        else if (g.lines[li9].kind === 'twig') twigs++;
      }
      var genLabel = g.gen === '␀' ? '未分组' : ('第 ' + g.gen + ' 代');
      var isActive = activeGen != null && String(g.gen) === String(activeGen);
      var ariaLabel = genLabel + (mainName ? (' · 主线 ' + mainName) : '') +
        ' · 共 ' + g.lines.length + ' 线 · ' + counts[gi] + ' 事' +
        (branches ? (' · ' + branches + ' 支线') : '') + (twigs ? (' · ' + twigs + ' 末梢') : '') +
        ' · 点击展开该代并滚动到位';
      cells.push(
        '<button type="button" class="cl-score-ovcell gen-' + (g.gen === '␀' ? 'x' : g.gen) + (isActive ? ' is-active' : '') + '"' +
        ' data-gen="' + esc(g.gen) + '" data-share="' + shareStr + '" data-grow="' + grow + '" aria-label="' + esc(ariaLabel) + '">' +
          '<span class="cl-score-ov-head"><span class="cl-score-ov-gen">' + esc(genLabel) + '</span>' +
          '<span class="cl-score-ov-events">' + counts[gi] + ' 事</span></span>' +
          (mainName
            ? '<span class="cl-score-ov-main" title="' + esc(mainName) + '">' + esc(mainName) + '</span>'
            : '<span class="cl-score-ov-main is-none">主线未定</span>') +
          '<span class="cl-score-ov-sub">' + g.lines.length + ' 线' +
            (branches ? (' · ' + branches + ' 支') : '') + (twigs ? (' · ' + twigs + ' 梢') : '') + '</span>' +
          overviewGanttSvg(g, cols, evIdx) +
        '</button>'
      );
    }
    return '<div class="cl-score-overview' + (compact ? ' is-compact' : '') + '" role="navigation"' +
      ' aria-label="代次总览轨 · ' + groups.length + ' 代" data-groups="' + groups.length + '">' + cells.join('') + '</div>';
  }

  // ---------------------------------------------------------------- 顶层 render（契约：render(model, opts?) 返回 HTML 字符串）
  function render(model, opts) {
    opts = opts || {};
    var maxChips = opts.maxChips || MAX_CHIPS;
    if (!model || model.ok === false) {
      var reason = (model && model.warnings && model.warnings[0] && model.warnings[0].msg) || (model && model.reason) || '剧情线谱数据不可用';
      return '<div class="cl-score-root cl-score-empty" role="status">' +
        '<p class="cl-score-empty-reason">' + esc(reason) + '</p></div>';
    }
    var cols = buildAxis(model);
    var initGeom = makeGeom(cols, MINCOL);
    var evIdx = buildEventIndex(model);
    var lines = arr(model.lines);
    var linesById = {}, li2;
    for (li2 = 0; li2 < lines.length; li2++) linesById[lines[li2].id] = lines[li2];
    var groupsInfo = computeGroups(model);
    var groups = groupsInfo.groups;
    var collapseAll = lines.length > MAX_FLAT_ROWS;
    var activeGen = currentActiveMainGen(lines);
    var expandGen = collapseAll ? activeGen : null;
    var badge = '';
    if (model.src === 'derived') badge = '<div class="cl-score-badge is-derived">结构为程序推导</div>';
    else if (model.src === 'mixed') badge = '<div class="cl-score-badge is-mixed">部分结构为程序推导</div>';
    var bodyParts = [];
    groups.forEach(function (g, gi) {
      var genLabel = g.gen === '␀' ? '代次未知' : ('第 ' + g.gen + ' 代');
      var genEventN = genEventCount(g);
      var genrowsHtml;
      var expandThis = expandGen != null && String(g.gen) === String(expandGen);
      if (collapseAll && !expandThis) {
        genrowsHtml = '<div class="cl-score-genrows is-collapsed" data-lazy="1" data-pending="' + g.lines.length + '"></div>';
      } else {
        var rowsHtml = g.lines.map(function (ln) {
          var uIdx = groupsInfo.unnamedIdx.hasOwnProperty(ln.id) ? groupsInfo.unnamedIdx[ln.id] : null;
          return renderRow(ln, cols, initGeom, evIdx, uIdx, false, linesById, maxChips, model);
        }).join('');
        genrowsHtml = '<div class="cl-score-genrows">' + rowsHtml + '</div>';
      }
      bodyParts.push(
        '<section class="cl-score-gen" role="rowgroup" data-gen="' + esc(g.gen) + '">' +
          '<div class="cl-score-genhead" role="button" tabindex="0" data-gen="' + esc(g.gen) + '" aria-expanded="' + (collapseAll && !expandThis ? 'false' : 'true') + '">' +
            '<span>' + esc(genLabel) + ' · ' + g.lines.length + ' 线 · ' + genEventN + ' 事</span>' +
          '</div>' +
          genrowsHtml +
        '</section>'
      );
      var nextG = groups[gi + 1];
      if (nextG && typeof g.gen === 'number' && typeof nextG.gen === 'number') {
        bodyParts.push(successionBannerHtml(findMainInGroup(g), findMainInGroup(nextG), evIdx, g.gen, nextG.gen));
      }
    });
    var orph = orphanEvents(model);
    bodyParts.push(orphanSectionHtml(model, cols, initGeom, evIdx, orph));
    var body = bodyParts.join('');
    var totals = model.totals || {};
    var conserveOk = model.conservation && num(model.conservation.rawThreads) != null
      ? (model.conservation.rawThreads === lines.length) : null;
    return (
      '<div class="cl-score-root" data-version="' + VERSION + '" data-lines="' + lines.length + '" data-conserve="' + (conserveOk === null ? 'unknown' : conserveOk) + '" tabindex="0" role="table" aria-label="剧情线谱">' +
        badge +
        renderAxis(cols, initGeom) +
        overviewRailHtml(model, groups, cols, evIdx, activeGen, !collapseAll) +
        '<div class="cl-score-body">' + body + '<svg class="cl-score-connections" aria-hidden="true">' + lines.filter(function (ln) {
          return ln.kind === 'main' && ln.handoff && ln.handoff.known && byId(lines, ln.handoff.fromId);
        }).map(function (ln) {
          return '<path class="cl-score-connection" data-from="' + esc(ln.handoff.fromId) + '" data-to="' + esc(ln.id) + '" data-gen="' + esc(ln.gen) + '"/>';
        }).join('') + '</svg></div>' +
        eventCardShell() +
      '</div>'
    );
  }

  // ---------------------------------------------------------------- R5-M：820 两级刻度列宽（主刻度列 > 次刻度列）
  function computeMajorMask(cols) {
    var n = cols.length, mask = new Array(n), i;
    for (i = 0; i < n; i++) mask[i] = (((i + 1) % AXIS_MAJOR_STEP) === 0) || (i === n - 1);
    return mask;
  }
  function computeTwoLevelWidths(cols, avail, majorMask) {
    var n = cols.length, base = new Array(n), totalBase = 0, i;
    for (i = 0; i < n; i++) { base[i] = majorMask[i] ? AXIS_MAJOR_W : AXIS_MINOR_W; totalBase += base[i]; }
    var scale = totalBase > 0 ? Math.max(1, avail / totalBase) : 1;
    var widths = new Array(n), totalW = 0;
    for (i = 0; i < n; i++) { widths[i] = base[i] * scale; totalW += widths[i]; }
    return { widths: widths, totalW: totalW };
  }
  // ---------------------------------------------------------------- 布局（宿主实测宽度 → 重建 track/axis 几何，零 style=）
  function layout(root, model, cols) {
    if (!root) return;
    var rowheadEl = root.querySelector('.cl-score-rowhead');
    var rowheadW = rowheadEl ? Math.max(88, rowheadEl.getBoundingClientRect().width) : 200;
    var hostW = root.clientWidth || (root.parentElement ? root.parentElement.clientWidth : 0) || 960;
    var avail = Math.max(200, hostW - rowheadW - 8);
    var tabletTwoLevel = hostW > NARROW_BP && hostW <= TABLET_BP;
    var majorMask = tabletTwoLevel ? computeMajorMask(cols) : null;
    var geom;
    if (tabletTwoLevel) {
      var tw = computeTwoLevelWidths(cols, avail, majorMask);
      geom = makeVarGeom(cols, tw.widths);
    } else {
      var colW = Math.max(MINCOL, avail / Math.max(1, cols.length));
      geom = makeGeom(cols, colW);
    }
    var totalW = geom.total;
    var evIdx = buildEventIndex(model);
    var narrowHost = hostW <= NARROW_BP;
    var dynMaxChips = narrowHost ? NARROW_MAX_CHIPS : MAX_CHIPS;

    var axisWrap = root.querySelector('.cl-score-axis');
    if (axisWrap) {
      var oldAxisSvg = axisWrap.querySelector('.cl-score-axis-svg');
      var tmpAxis = document.createElement('div'); tmpAxis.innerHTML = buildAxisSvgHtml(cols, geom, majorMask);
      if (oldAxisSvg) axisWrap.replaceChild(tmpAxis.firstChild, oldAxisSvg);
    }

    var ovCells = root.querySelectorAll('.cl-score-ovcell[data-grow]');
    for (var oi = 0; oi < ovCells.length; oi++) {
      ovCells[oi].style.flexGrow = ovCells[oi].getAttribute('data-grow');
      ovCells[oi].style.animationDelay = (oi * 26) + 'ms';
    }

    var lines = arr(model.lines), lineById = {}, j;
    for (j = 0; j < lines.length; j++) lineById[lines[j].id] = lines[j];
    var wideHost = hostW >= 1100;
    var tracks = root.querySelectorAll('.cl-score-track[data-line-id]');
    for (var i = 0; i < tracks.length; i++) {
      var lid = tracks[i].getAttribute('data-line-id');
      var ln = lineById[lid];
      if (!ln) continue;
      var t = buildTrack(ln, cols, geom, evIdx, lineById);
      var remaining = t.totalW - t.barTailX;
      var inline = wideHost && remaining >= 260;
      var svgHtml = t.html;
      if (inline) svgHtml += castForeignObjectHtml(ln, t.barTailX + 8, remaining - 16, t.rowH, dynMaxChips);
      svgHtml += '</svg>';
      var frag = document.createElement('div'); frag.innerHTML = svgHtml + (inline ? '' : castStandaloneHtml(ln, dynMaxChips));
      tracks[i].innerHTML = '';
      while (frag.firstChild) tracks[i].appendChild(frag.firstChild);
      tracks[i].classList.toggle('is-cast-inline', inline);
    }
    var orphTrack = root.querySelector('.cl-score-orphan-track');
    if (orphTrack) {
      var orph2 = orphanEvents(model);
      var tmpOrph = document.createElement('div'); tmpOrph.innerHTML = buildOrphanTrack(orph2.idxs, cols, geom, evIdx);
      orphTrack.innerHTML = '';
      while (tmpOrph.firstChild) orphTrack.appendChild(tmpOrph.firstChild);
    }
    return { geom: geom, totalW: totalW, cols: cols };
  }

  // ---------------------------------------------------------------- mount（契约 §2：返回 setFocus/setFilter/resize/step/dispose）
  function mount(host, opts) {
    opts = opts || {};
    if (!host) throw new Error('CLAtlasScore.mount: host required');
    if (host.__clAtlasScoreDispose) { try { host.__clAtlasScoreDispose(); } catch (eDup) {} }

    var model = opts.model;
    var disposed = false;
    var cols = buildAxis(model);
    var evIdx = buildEventIndex(model);
    var state = { filter: { kinds: null, gens: null, q: '' }, focusLineId: null, focusEventIdx: null };
    var rowOrder = [];
    var groupsInfo = model && model.ok !== false ? computeGroups(model) : { groups: [], unnamedIdx: {} };
    var linesById = {};
    (function () {
      var ls = arr(model && model.lines), i5;
      for (i5 = 0; i5 < ls.length; i5++) linesById[ls[i5].id] = ls[i5];
    })();

    host.innerHTML = render(model);
    var root = host.querySelector('.cl-score-root');

    function collectRowOrder() {
      rowOrder = root ? Array.prototype.slice.call(root.querySelectorAll('.cl-score-row')) : [];
    }
    collectRowOrder();

    function updateConnections() {
      if (!root) return;
      var body = root.querySelector('.cl-score-body'), svg = root.querySelector('.cl-score-connections');
      if (!body || !svg) return;
      var box = body.getBoundingClientRect();
      svg.setAttribute('width', body.scrollWidth); svg.setAttribute('height', body.offsetHeight);
      var paths = svg.querySelectorAll('.cl-score-connection');
      for (var p = 0; p < paths.length; p++) {
        var path = paths[p], rows = root.querySelectorAll('.cl-score-row'), from = null, to = null;
        for (var r = 0; r < rows.length; r++) {
          if (rows[r].getAttribute('data-line-id') === path.getAttribute('data-from')) from = rows[r];
          if (rows[r].getAttribute('data-line-id') === path.getAttribute('data-to')) to = rows[r];
        }
        var a = from && from.querySelector('.cl-score-svg .cl-score-cap-end');
        var b = to && to.querySelector('.cl-score-svg .cl-score-cap-start');
        if (!a || !b || !a.getClientRects().length || !b.getClientRects().length) { path.removeAttribute('d'); continue; }
        var ab = a.getBoundingClientRect(), bb = b.getBoundingClientRect();
        var x1 = ab.left + ab.width / 2 - box.left, y1 = ab.top + ab.height / 2 - box.top;
        var x2 = bb.left + bb.width / 2 - box.left, y2 = bb.top + bb.height / 2 - box.top;
        path.setAttribute('d', 'M' + x1 + ',' + y1 + ' V' + (y2 - 16) + ' H' + x2 + ' V' + y2);
      }
    }
    function highlightCharacter() {
      if (!root) return;
      var name = root.getAttribute('data-footprint-character'), ticks = root.querySelectorAll('.cl-score-tick');
      root.classList.toggle('has-character-footprint', !!name);
      for (var i = 0; i < ticks.length; i++) {
        var ev = evIdx[+ticks[i].getAttribute('data-event-idx')];
        ticks[i].classList.toggle('is-character-footprint', !!name && !!ev && arr(ev.cast).indexOf(name) >= 0);
      }
      var chips = root.querySelectorAll('.cl-score-chip[data-character]');
      for (var j = 0; j < chips.length; j++) chips[j].setAttribute('aria-pressed', String(!!name && chips[j].getAttribute('data-character') === name));
    }
    function doLayout() { if (root && model && model.ok !== false) { layout(root, model, cols); highlightCharacter(); updateConnections(); } }
    doLayout();

    // ---- R3-D #4：惰性组实体化——组头首次展开时才把该组的行 HTML 建进 DOM（首屏 render()
    function materializeGroup(genSection) {
      if (!genSection) return null;
      var rowsWrap = genSection.querySelector('.cl-score-genrows');
      if (!rowsWrap || rowsWrap.getAttribute('data-lazy') !== '1') return null;
      var gen = genSection.getAttribute('data-gen');
      var group = null, gi;
      for (gi = 0; gi < groupsInfo.groups.length; gi++) {
        if (String(groupsInfo.groups[gi].gen) === String(gen)) { group = groupsInfo.groups[gi]; break; }
      }
      if (!group) return null;
      var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
      var html = group.lines.map(function (ln) {
        var uIdx = groupsInfo.unnamedIdx.hasOwnProperty(ln.id) ? groupsInfo.unnamedIdx[ln.id] : null;
        return renderRow(ln, cols, makeGeom(cols, MINCOL), evIdx, uIdx, false, linesById, MAX_CHIPS, model);
      }).join('');
      var frag = document.createElement('div'); frag.innerHTML = html;
      while (frag.firstChild) rowsWrap.appendChild(frag.firstChild);
      rowsWrap.removeAttribute('data-lazy');
      rowsWrap.removeAttribute('data-pending');
      collectRowOrder();
      doLayout();
      var t1 = (window.performance && performance.now) ? performance.now() : Date.now();
      return { ms: t1 - t0, rows: group.lines.length };
    }

    function lineIdOf(el) { return el ? el.getAttribute('data-line-id') : null; }
    function expandGenAndScroll(gen) {
      if (!root || gen == null) return;
      var sec = root.querySelector('.cl-score-gen[data-gen="' + String(gen).replace(/"/g, '') + '"]');
      if (!sec) return;
      var rows = sec.querySelector('.cl-score-genrows');
      var head = sec.querySelector('.cl-score-genhead');
      if (rows) {
        if (rows.getAttribute('data-lazy') === '1') materializeGroup(sec);
        if (rows.classList.contains('is-collapsed')) {
          rows.classList.remove('is-collapsed');
          if (head) head.setAttribute('aria-expanded', 'true');
        }
      }
      updateConnections(); highlightCharacter();
      try { sec.scrollIntoView({ block: 'start', inline: 'nearest', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); } catch (eS) {}
    }
    function findRowByLineId(id) {
      for (var i = 0; i < rowOrder.length; i++) { if (rowOrder[i].getAttribute('data-line-id') === String(id)) return rowOrder[i]; }
      return null;
    }
    function prefersReducedMotion() {
      try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (eM) { return false; }
    }
    function clearFocusClasses() {
      if (!root) return;
      var f = root.querySelectorAll('.is-focused');
      for (var i = 0; i < f.length; i++) f[i].classList.remove('is-focused');
    }
    function updateGenProximity(row) {
      if (!root) return;
      var sections = Array.prototype.slice.call(root.querySelectorAll('.cl-score-gen'));
      var curSection = row && row.closest ? row.closest('.cl-score-gen') : null;
      var curIdx = curSection ? sections.indexOf(curSection) : -1;
      for (var i = 0; i < sections.length; i++) {
        var near = curIdx >= 0 && (i === curIdx || i === curIdx - 1 || i === curIdx + 1);
        sections[i].classList.toggle('is-gen-near', near);
      }
    }
    function clearGenProximity() {
      if (!root) return;
      var sections = root.querySelectorAll('.cl-score-gen.is-gen-near');
      for (var i = 0; i < sections.length; i++) sections[i].classList.remove('is-gen-near');
    }
    function focusRow(row, opts2) {
      if (!row) return;
      clearFocusClasses();
      row.classList.add('is-focused');
      state.focusLineId = row.getAttribute('data-line-id');
      if (root) root.classList.add('is-score-dimmed');
      updateGenProximity(row);
      if (!(opts2 && opts2.noScroll)) {
        try { row.scrollIntoView({ block: 'center', inline: 'nearest', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); } catch (eSc) {}
      }
    }
    function focusEvent(lineIdOrNull, eventIdx) {
      if (!root) return;
      var scope = lineIdOrNull != null ? root.querySelector('.cl-score-track[data-line-id="' + String(lineIdOrNull).replace(/"/g, '') + '"]') : root;
      if (!scope) scope = root;
      var tick = scope.querySelector('.cl-score-tick[data-event-idx="' + eventIdx + '"]');
      if (tick) {
        tick.classList.add('is-focused');
        state.focusEventIdx = eventIdx;
        try { tick.scrollIntoView({ block: 'nearest', inline: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' }); } catch (eSc) {}
      }
    }

    // ---- 事件卡（主控二轮修正：重设计成层级卡片，见 eventCardBodyHtml；定位靠近被点行，
    function isCardOpen() {
      var panel = root && root.querySelector('.cl-score-eventcard');
      return !!(panel && !panel.classList.contains('is-hidden'));
    }
    function positionEventCard(panel, rowEl, tickEl) {
      if (!root || !rowEl || !panel) return;
      var bodyEl = root.querySelector('.cl-score-body');
      if (!bodyEl) return;
      var rowTop = bodyEl.offsetTop + rowEl.offsetTop;
      var rowH2 = rowEl.offsetHeight;
      var rowRect = rowEl.getBoundingClientRect();
      var gap = 8;
      var estH = panel.offsetHeight || 220;
      var viewportH = window.innerHeight || 900;
      var spaceBelow = viewportH - rowRect.bottom;
      var placeAbove = spaceBelow < (estH + gap) && rowRect.top > (estH + gap);
      panel.classList.remove('is-pos-above', 'is-pos-below');
      panel.classList.add(placeAbove ? 'is-pos-above' : 'is-pos-below');
      var top = placeAbove ? (rowTop - estH - gap) : (rowTop + rowH2 + gap);
      if (top < 0) top = 0;
      panel.style.top = top + 'px';

      if (!tickEl || typeof tickEl.getBoundingClientRect !== 'function') {
        panel.style.left = '';
        panel.style.right = '';
        panel.classList.remove('is-anchor-flip');
        return;
      }
      var rowheadEl = root.querySelector('.cl-score-rowhead');
      var rowheadRect = rowheadEl ? rowheadEl.getBoundingClientRect() : null;
      var minLeftVp = (rowheadRect ? rowheadRect.right : 0) + 4;
      var bodyRect = bodyEl.getBoundingClientRect();
      var tickRect = tickEl.getBoundingClientRect();
      var estW = panel.offsetWidth || 320;
      var viewportW = window.innerWidth || 1200;
      var maxLeftVp = Math.max(minLeftVp, viewportW - estW - 8);
      var spaceRight = viewportW - tickRect.right;
      var flipLeft = spaceRight < (estW + gap) && (tickRect.left - minLeftVp) >= estW;
      var placedLeftVp = flipLeft ? (tickRect.left - estW - gap) : tickRect.left;
      placedLeftVp = clamp(placedLeftVp, minLeftVp, maxLeftVp);
      panel.style.left = (placedLeftVp - bodyRect.left) + 'px';
      panel.style.right = 'auto';
      panel.classList.toggle('is-anchor-flip', flipLeft);
    }
    function findTickForEvent(rowEl, ei) {
      var scope = rowEl || root;
      return scope ? scope.querySelector('.cl-score-tick[data-event-idx="' + ei + '"]') : null;
    }
    function showEventCard(ei, rowEl) {
      if (!root) return;
      var panel = root.querySelector('.cl-score-eventcard');
      if (!panel) return;
      var e = evIdx[ei] || null;
      var body = panel.querySelector('.cl-score-eventcard-body');
      if (body) body.innerHTML = eventCardBodyHtml(e, model);
      panel.classList.remove('is-hidden');
      panel.setAttribute('aria-hidden', 'false');
      var bq = panel.querySelector('.cl-score-card-quote-text');
      var qToggle = panel.querySelector('[data-quote-toggle]');
      if (bq && qToggle) { qToggle.hidden = !(bq.scrollHeight > bq.clientHeight + 1); }
      var anchorRow = rowEl || (e && Array.isArray(e.lineIds) && e.lineIds.length ? findRowByLineId(e.lineIds[0]) : null);
      if (anchorRow) positionEventCard(panel, anchorRow, findTickForEvent(anchorRow, ei));
    }
    function hideEventCard() {
      if (!root) return;
      var panel = root.querySelector('.cl-score-eventcard');
      if (panel) { panel.classList.add('is-hidden'); panel.setAttribute('aria-hidden', 'true'); }
    }
    function openEvent(ei, rowEl) {
      focusEvent(rowEl ? rowEl.getAttribute('data-line-id') : null, ei);
      showEventCard(ei, rowEl);
      if (typeof opts.onEvent === 'function') opts.onEvent(ei);
    }

    // ---- 事件委托：click
    function onClick(e) {
      var t = e.target;
      var cardClose = t.closest && t.closest('[data-eventcard-close]');
      if (cardClose) { hideEventCard(); return; }
      var ovcell = t.closest && t.closest('.cl-score-ovcell');
      if (ovcell) { expandGenAndScroll(ovcell.getAttribute('data-gen')); return; }
      var genhead = t.closest && t.closest('.cl-score-genhead');
      if (genhead) {
        var genSection = genhead.parentElement;
        var rows = genSection.querySelector('.cl-score-genrows');
        if (rows) {
          if (rows.getAttribute('data-lazy') === '1') materializeGroup(genSection);
          var collapsed = rows.classList.toggle('is-collapsed');
          genhead.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
          updateConnections(); highlightCharacter();
        }
        return;
      }
      var more = t.closest && t.closest('.cl-score-chip-more');
      if (more) {
        var cast = more.closest('.cl-score-cast');
        var expanded = cast.classList.toggle('is-expanded');
        more.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        var sib = cast.nextElementSibling;
        if (sib && sib.classList && sib.classList.contains('cl-score-cast-more')) { sib.hidden = !expanded; }
        updateConnections();
        return;
      }
      var qToggle2 = t.closest && t.closest('[data-quote-toggle]');
      if (qToggle2) {
        var fig = qToggle2.closest('.cl-score-card-quote');
        if (fig) {
          var wasExpanded = fig.getAttribute('data-quote-state') === 'expanded';
          fig.setAttribute('data-quote-state', wasExpanded ? 'collapsed' : 'expanded');
          qToggle2.textContent = wasExpanded ? '展开' : '收起';
          qToggle2.setAttribute('aria-expanded', wasExpanded ? 'false' : 'true');
        }
        return;
      }
      var locateBtn = t.closest && t.closest('[data-locate-event]');
      if (locateBtn) {
        var eiLoc = +locateBtn.getAttribute('data-locate-event');
        try { document.dispatchEvent(new CustomEvent('cl:atlas-locate', { detail: { eventIdx: eiLoc } })); } catch (eDisp) {}
        return;
      }
      var chip = t.closest && t.closest('.cl-score-chip[data-character]');
      if (chip) {
        var character = chip.getAttribute('data-character');
        var selected = root.getAttribute('data-footprint-character') !== character;
        if (selected) root.setAttribute('data-footprint-character', character);
        else root.removeAttribute('data-footprint-character');
        highlightCharacter();
        if (selected && typeof opts.onCharacter === 'function') opts.onCharacter(character);
        return;
      }
      var tickHit = t.closest && (t.closest('.cl-score-tick-hit') || t.closest('.cl-score-tick'));
      if (tickHit && tickHit.getAttribute) {
        var eiAttr = tickHit.getAttribute('data-event-idx');
        if (eiAttr != null && eiAttr !== '') {
          openEvent(+eiAttr, tickHit.closest('.cl-score-row') || tickHit.closest('.cl-score-orphan'));
          return;
        }
      }
      var rowhead = t.closest && t.closest('.cl-score-rowhead[data-line-id]');
      if (rowhead) {
        var row = findRowByLineId(rowhead.getAttribute('data-line-id'));
        focusRow(row, { noScroll: true });
        if (typeof opts.onLine === 'function') opts.onLine(rowhead.getAttribute('data-line-id'));
      }
    }
    host.addEventListener('click', onClick);

    // ---- 事件委托：keydown（↑↓ 换行、←→ 换事件、Enter 打开、Esc 返回）
    function isTextInput(el) {
      if (!el) return false;
      var tag = (el.tagName || '').toLowerCase();
      return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
    }
    var curRowIdx = -1, curEventList = [], curEventPos = -1;
    function refreshEventListFor(row) {
      curEventList = row ? Array.prototype.slice.call(row.querySelectorAll('.cl-score-tick')) : [];
      curEventPos = -1;
    }
    function onKeydown(e) {
      if (isTextInput(document.activeElement)) return;
      if (disposed) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); e.stopPropagation();
        if (!rowOrder.length) return;
        curRowIdx = curRowIdx < 0 ? 0 : clamp(curRowIdx + (e.key === 'ArrowDown' ? 1 : -1), 0, rowOrder.length - 1);
        var row = rowOrder[curRowIdx];
        focusRow(row);
        refreshEventListFor(row);
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault(); e.stopPropagation();
        if (curRowIdx < 0 && rowOrder.length) { curRowIdx = 0; focusRow(rowOrder[0]); refreshEventListFor(rowOrder[0]); }
        if (!curEventList.length) return;
        curEventPos = curEventPos < 0 ? 0 : clamp(curEventPos + (e.key === 'ArrowRight' ? 1 : -1), 0, curEventList.length - 1);
        var tickEl = curEventList[curEventPos];
        var ei = +tickEl.getAttribute('data-event-idx');
        var curRowForNav = rowOrder[curRowIdx] || null;
        focusEvent(curRowForNav ? curRowForNav.getAttribute('data-line-id') : null, ei);
        if (isCardOpen()) {
          showEventCard(ei, curRowForNav);
          if (typeof opts.onEvent === 'function') opts.onEvent(ei);
        }
      } else if (e.key === 'Enter' || e.key === ' ') {
        var ovTarget = e.target && e.target.closest && e.target.closest('.cl-score-ovcell');
        if (ovTarget) return;
        var genheadTarget = e.target && e.target.closest && e.target.closest('.cl-score-genhead');
        if (genheadTarget) {
          e.preventDefault(); e.stopPropagation();
          var genSectionKb = genheadTarget.parentElement;
          var grows = genSectionKb.querySelector('.cl-score-genrows');
          if (grows) {
            if (grows.getAttribute('data-lazy') === '1') materializeGroup(genSectionKb);
            var coll = grows.classList.toggle('is-collapsed');
            genheadTarget.setAttribute('aria-expanded', coll ? 'false' : 'true');
          }
          return;
        }
        if (e.key !== 'Enter') return;
        e.preventDefault(); e.stopPropagation();
        if (curEventPos >= 0 && curEventList[curEventPos]) {
          openEvent(+curEventList[curEventPos].getAttribute('data-event-idx'), rowOrder[curRowIdx] || null);
        } else if (curRowIdx >= 0 && rowOrder[curRowIdx]) {
          if (typeof opts.onLine === 'function') opts.onLine(rowOrder[curRowIdx].getAttribute('data-line-id'));
        }
      } else if (e.key === 'Escape') {
        if (isCardOpen()) { e.preventDefault(); e.stopPropagation(); hideEventCard(); return; }
        if (typeof opts.onBack === 'function') opts.onBack();
      }
    }
    host.addEventListener('keydown', onKeydown, true);

    // ---- API
    function setFocus(f) {
      if (f == null) {
        clearFocusClasses();
        clearGenProximity();
        if (root) root.classList.remove('is-score-dimmed');
        state.focusLineId = null; state.focusEventIdx = null;
        curRowIdx = -1; curEventList = []; curEventPos = -1;
        return;
      }
      var targetLine = f.lineId;
      if (targetLine == null && f.character != null && model) {
        var lines = arr(model.lines), i, cast;
        for (i = 0; i < lines.length; i++) {
          cast = arr(lines[i].cast);
          if (cast.some(function (c) { return c && c.name === f.character; })) { targetLine = lines[i].id; break; }
        }
      }
      if (targetLine != null) {
        ensureLineRendered(targetLine);
        var row = findRowByLineId(targetLine);
        if (row) { focusRow(row); refreshEventListFor(row); curRowIdx = rowOrder.indexOf(row); }
      }
      if (f.eventIdx != null) { focusEvent(targetLine, f.eventIdx); }
    }
    function ensureLineRendered(lineId) {
      if (!root || lineId == null || findRowByLineId(lineId)) return;
      var lsAll = arr(model && model.lines), target = null, k6;
      for (k6 = 0; k6 < lsAll.length; k6++) { if (idEq(lsAll[k6].id, lineId) || String(lsAll[k6].id) === String(lineId)) { target = lsAll[k6]; break; } }
      if (!target) return;
      var gen = target.gen == null ? '␀' : target.gen;
      var genSection = root.querySelector('.cl-score-gen[data-gen="' + String(gen).replace(/"/g, '') + '"]');
      if (!genSection) return;
      var rw2 = genSection.querySelector('.cl-score-genrows');
      if (rw2 && rw2.getAttribute('data-lazy') === '1') materializeGroup(genSection);
    }
    function matchLine(ln, filter) {
      if (filter.kinds && filter.kinds.length && filter.kinds.indexOf(ln.kind) < 0) return false;
      if (filter.gens && filter.gens.length && filter.gens.indexOf(ln.gen) < 0) return false;
      if (filter.q) {
        var q = String(filter.q).toLowerCase();
        var hay = [ln.name, ln.lead && ln.lead.name].concat(arr(ln.cast).map(function (c) { return c.name; })).filter(Boolean).join(' ').toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    }
    function setFilter(f) {
      state.filter = { kinds: f && f.kinds || null, gens: f && f.gens || null, q: f && f.q || '' };
      if (!model) return;
      var hasActiveFilter = !!(state.filter.q || (state.filter.kinds && state.filter.kinds.length) || (state.filter.gens && state.filter.gens.length));
      if (hasActiveFilter && root) {
        var lazySections = Array.prototype.slice.call(root.querySelectorAll('.cl-score-gen[data-gen]'));
        for (var gi2 = 0; gi2 < lazySections.length; gi2++) {
          var rw = lazySections[gi2].querySelector('.cl-score-genrows');
          if (rw && rw.getAttribute('data-lazy') === '1') materializeGroup(lazySections[gi2]);
        }
      }
      var lines = arr(model.lines), byIdMap = {}, i;
      for (i = 0; i < lines.length; i++) byIdMap[lines[i].id] = lines[i];
      for (i = 0; i < rowOrder.length; i++) {
        var row = rowOrder[i], ln = byIdMap[row.getAttribute('data-line-id')];
        if (!ln) continue;
        row.classList.toggle('is-filtered-out', !matchLine(ln, state.filter));
      }
      if (state.filter.q && root) {
        var sections = Array.prototype.slice.call(root.querySelectorAll('.cl-score-gen[data-gen]'));
        for (var gi3 = 0; gi3 < sections.length; gi3++) {
          var rowsWrap2 = sections[gi3].querySelector('.cl-score-genrows');
          var head2 = sections[gi3].querySelector('.cl-score-genhead');
          if (!rowsWrap2 || !head2) continue;
          var hasMatch = !!rowsWrap2.querySelector('.cl-score-row:not(.is-filtered-out)');
          if (hasMatch && rowsWrap2.classList.contains('is-collapsed')) {
            rowsWrap2.classList.remove('is-collapsed');
            head2.setAttribute('aria-expanded', 'true');
          }
        }
      }
      updateConnections(); highlightCharacter();
    }
    function resize() { doLayout(); collectRowOrder(); }
    function step() { return true; }
    function dispose() {
      if (disposed) return;
      disposed = true;
      host.removeEventListener('click', onClick);
      host.removeEventListener('keydown', onKeydown, true);
      host.innerHTML = '';
      delete host.__clAtlasScoreDispose;
    }
    host.__clAtlasScoreDispose = dispose;

    return { setFocus: setFocus, setFilter: setFilter, resize: resize, step: step, dispose: dispose };
  }

  window.CLAtlasScore = { VERSION: VERSION, render: render, mount: mount };
})();
