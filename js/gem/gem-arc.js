// @role component
// @owns js/gem/gem-arc.js
// @budget dom_nodes <= 120; js_ms <= 0.5; drawcalls += 0
// @contract v80-W3
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var X0 = 8;
  var X1 = 352;
  var SPAN = X1 - X0;
  var svg = null;
  var st = { hits: 0, lines: 0, chapters: 0 };
  var activeModel = null;

  function tokenPx(name, fb) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    var n = parseFloat(v);
    return isNaN(n) ? fb : n;
  }

  function mk(tag, cls) {
    var node = document.createElementNS(NS, tag);
    if (cls) node.setAttribute('class', cls);
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function toInt(v, fb) {
    var n = Math.floor(Number(v));
    return isFinite(n) ? n : fb;
  }

  function cellX(i, n) {
    return X0 + (SPAN * i) / n;
  }

  function cellC(i, n) {
    return X0 + (SPAN * (i + 0.5)) / n;
  }

  function clamp(i, n) {
    if (!(i > 0)) return 0;
    if (i > n - 1) return n - 1;
    return i;
  }

  function px(v) {
    return String(Math.round(v * 100) / 100);
  }

  function drawNa(h) {
    var t = mk('text', 'cl-gem-arc__na');
    t.setAttribute('x', String(X0));
    t.setAttribute('y', String(Math.round(h / 2)));
    t.setAttribute('text-anchor', 'start');
    t.appendChild(document.createTextNode('章节足迹未就绪'));
    svg.appendChild(t);
  }

  function drawHits(M) {
    var n = st.chapters;
    var hits = (M.arc && M.arc.hits) || [];
    var bins = Math.min(n, 80), buckets = [], cw = SPAN / bins;
    var max = 1;
    var i;
    for (i = 0; i < bins; i++) {
      var start = Math.floor(i * n / bins), end = Math.floor((i + 1) * n / bins) - 1, total = 0;
      for (var ch = start; ch <= end; ch++) total += toInt(hits[ch], 0);
      buckets.push({ start: start, end: end, count: total });
      if (total > max) max = total;
    }
    for (i = 0; i < bins; i++) {
      var bucket = buckets[i], hit = bucket.count;
      var bh = Math.round((hit / max) * 22);
      var cls = 'cl-gem-arc__hit';
      if (hit <= 0) cls += ' is-zero';
      var r = mk('rect', cls);
      r.setAttribute('data-ch', String(bucket.start));
      r.setAttribute('data-ch-end', String(bucket.end));
      var evs = (M.arc && M.arc.events) || [], first = null;
      for (var ei = 0; ei < evs.length; ei++) {
        if (evs[ei] && evs[ei].chapIdx >= bucket.start && evs[ei].chapIdx <= bucket.end) { first = evs[ei]; break; }
      }
      if (first) {
        r.setAttribute('data-event-idx', String(first.eventIdx));
        if (first.order !== null && first.order !== undefined) r.setAttribute('data-order', String(first.order));
      }
      r.setAttribute('tabindex', '0');
      r.setAttribute('role', 'button');
      r.setAttribute('aria-label', '第 ' + String(bucket.start + 1) + (bucket.end > bucket.start ? '–' + String(bucket.end + 1) : '') + ' 章足迹' + (hit ? ' · ' + hit + ' 个已知事件' : ' · 尚无事件记录'));
      r.setAttribute('x', px(cellX(i, bins)));
      r.setAttribute('width', px(cw));
      r.setAttribute('height', String(bh));
      r.setAttribute('y', String(30 - bh));
      svg.appendChild(r);
      st.hits++;
    }
  }

  function drawLines(M) {
    var n = st.chapters;
    var barH = tokenPx('--cl-gem-arc-bar-h', 4);
    var rowH = barH + 2;
    var lines = (M.arc && M.arc.lines) || [];
    var i;
    for (i = 0; i < lines.length; i++) {
      var L = lines[i];
      if (!L) continue;
      var row = i < 4 ? i : 3;
      var e = clamp(toInt(L.entryChap, 0), n);
      var x = clamp(toInt(L.exitChap, e), n);
      if (x < e) x = e;
      var x1 = cellX(e, n);
      var x2 = cellX(x + 1, n);
      var cls = 'cl-gem-arc__line';
      if (L.role === 'lead') cls += ' is-lead';
      if (i >= 4) cls += ' is-stack';
      var w = x2 - x1;
      if (w < 1) w = 1;
      var r = mk('rect', cls);
      r.setAttribute('data-id', String(L.id));
      r.setAttribute('data-ch', String(e));
      var events = (M.arc && M.arc.events) || [], point = null;
      for (var ei = 0; ei < events.length; ei++) {
        if (events[ei].lineIds && events[ei].lineIds.indexOf(L.id) >= 0) { point = events[ei]; break; }
      }
      if (point) r.setAttribute('data-event-idx', String(point.eventIdx));
      r.setAttribute('tabindex', '0'); r.setAttribute('role', 'button');
      r.setAttribute('aria-label', (L.name || '剧情线') + ' · 定位角色足迹');
      if (L.gen != null) r.setAttribute('data-gen', String(L.gen));
      r.setAttribute('x', px(x1));
      r.setAttribute('width', px(w));
      r.setAttribute('y', String(Math.round(36 + row * rowH)));
      r.setAttribute('height', String(barH));
      svg.appendChild(r);
      st.lines++;
    }
  }

  function tri(cls, cx) {
    var c = Math.round(cx * 100) / 100;
    var p = mk('path', cls);
    p.setAttribute('d', 'M ' + (c - 2) + ' 30 L ' + (c + 2) + ' 30 L ' + c + ' 34 Z');
    return p;
  }

  function drawMarks(M) {
    var n = st.chapters;
    var first = M.arc.first;
    var last = M.arc.last;
    if (first != null && first >= 0) {
      svg.appendChild(tri('cl-gem-arc__in', cellC(clamp(toInt(first, 0), n), n)));
    }
    if (last != null && last >= 0) {
      svg.appendChild(tri('cl-gem-arc__out', cellC(clamp(toInt(last, 0), n), n)));
    }
  }

  function drawNums(h) {
    var n = st.chapters;
    var step = Math.max(1, Math.ceil(n / 8));
    var i;
    for (i = 0; i < n; i += step) {
      var t = mk('text', 'cl-gem-arc__num');
      t.setAttribute('x', px(cellC(i, n)));
      t.setAttribute('y', String(h - 4));
      t.setAttribute('text-anchor', 'middle');
      t.appendChild(document.createTextNode(String(i + 1)));
      svg.appendChild(t);
    }
  }

  function build(M) {
    if (!svg) return;
    clear(svg);
    st.hits = 0;
    st.lines = 0;
    st.chapters = 0;
    activeModel = M || null;
    var h = tokenPx('--cl-gem-arc-h', 56);
    if (!M || !M.arc || M.arc.known === false) {
      drawNa(h);
      return;
    }
    var n = toInt(M.arc.chapters, 0);
    if (n <= 0) {
      drawNa(h);
      return;
    }
    st.chapters = n;
    drawHits(M);
    drawLines(M);
    drawMarks(M);
    drawNums(h);
  }

  function mount(host, M) {
    unmount();
    var h = tokenPx('--cl-gem-arc-h', 56);
    svg = mk('svg', 'cl-gem-arc');
    svg.setAttribute('viewBox', '0 0 360 ' + h);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('width', '100%');
    svg.setAttribute('role', 'group');
    svg.setAttribute('aria-label', '角色章节足迹 · 点击或回车定位真实事件');
    host.appendChild(svg);
    svg.addEventListener('click', onActivate, false);
    svg.addEventListener('keydown', onActivate, false);
    build(M);
    return svg;
  }

  function update(M) {
    build(M);
  }

  function unmount() {
    if (svg) {
      svg.removeEventListener('click', onActivate, false);
      svg.removeEventListener('keydown', onActivate, false);
      if (svg.parentNode) svg.parentNode.removeChild(svg);
    }
    svg = null;
    activeModel = null;
    st.hits = 0;
    st.lines = 0;
    st.chapters = 0;
  }

  function stats() {
    return { hits: st.hits, lines: st.lines, chapters: st.chapters };
  }

  function eventForTarget(target) {
    var n = target;
    while (n && n !== svg) {
      if (n.getAttribute && (n.getAttribute('data-ch') !== null || n.getAttribute('data-event-idx') !== null)) break;
      n = n.parentNode;
    }
    if (!n || n === svg || !activeModel || !activeModel.arc) return null;
    var events = activeModel.arc.events || [], idx = n.getAttribute('data-event-idx');
    var found = null, i;
    if (idx !== null) {
      for (i = 0; i < events.length; i++) {
        if (String(events[i].eventIdx) === String(idx)) { found = events[i]; break; }
      }
    }
    if (!found) {
      var ch = toInt(n.getAttribute('data-ch'), -1);
      for (i = 0; i < events.length; i++) {
        if (events[i].chapIdx === ch) { found = events[i]; break; }
      }
    }
    return {
      name: activeModel.name || null,
      eventIdx: found ? found.eventIdx : null,
      order: found ? found.order : null,
      chapIdx: found ? found.chapIdx : toInt(n.getAttribute('data-ch'), null),
      chapter: found ? found.chapter : null,
      title: found ? found.title : null,
      kind: found ? found.kind : null,
      lineId: n.getAttribute('data-id'),
      lineIds: found && found.lineIds ? found.lineIds.slice(0) : []
    };
  }

  function onActivate(ev) {
    if (ev.type === 'keydown' && ev.key !== 'Enter' && ev.key !== ' ' && ev.key !== 'Spacebar') return;
    var detail = eventForTarget(ev.target);
    if (!detail) return;
    if (ev.preventDefault) ev.preventDefault();
    try { document.dispatchEvent(new CustomEvent('cl:gem-event', { detail: detail, bubbles: true })); } catch (e) {}
  }

  window.CLGemArc = {
    name: 'gem-arc',
    version: 'v80',
    mount: mount,
    update: update,
    unmount: unmount,
    stats: stats
  };
})();
