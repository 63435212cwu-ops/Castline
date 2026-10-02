/* Local geometric expansion, shared by the three atlas lenses. Every star maps to an existing record. */
(function (g) {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg', host = null, input = null, page = 0, pageSize = 12, selected = null, focusNode = -1;
  function node(tag, attrs, text) {
    var el = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (text != null) el.textContent = text;
    return el;
  }
  function button(svg, x, y, label, fn) {
    var b = node('g', { 'class': 'atlas-local-page', role: 'button', tabindex: 0, 'aria-label': label, transform: 'translate(' + x + ',' + y + ')' });
    b.appendChild(node('rect', { x: -37, y: -19, width: 74, height: 38, rx: 4 })); b.appendChild(node('text', { y: 5 }, label));
    b.addEventListener('click', fn); b.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); fn(); } }); svg.appendChild(b);
  }
  function draw() {
    if (!input || !host) return;
    var W = innerWidth, H = innerHeight, top = W < 480 ? 235 : 180, bottom = 165, available = Math.max(160, H - top - bottom);
    var radius = Math.min(W * .35, available * .38, 240), cx = W / 2, cy = top + available / 2;
    var mobile = W < 600, nodes = input.nodes || []; pageSize = mobile ? 6 : 12;
    page = Math.max(0, Math.min(page, Math.ceil(nodes.length / pageSize) - 1));
    var shown = nodes.slice(page * pageSize, (page + 1) * pageSize);
    host.replaceChildren(); var svg = node('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'group', 'aria-label': input.title });
    svg.appendChild(node('circle', { 'class': 'atlas-local-well', cx: cx, cy: cy, r: radius + (mobile ? 45 : 70) }));
    svg.appendChild(node('circle', { 'class': 'atlas-local-orbit', cx: cx, cy: cy, r: radius }));
    svg.appendChild(node('circle', { 'class': 'atlas-local-orbit', cx: cx, cy: cy, r: radius * .42 }));
    var defs = node('defs'), marker = node('marker', { id: 'atlas-local-arrow', viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto-start-reverse' });
    marker.appendChild(node('path', { d: 'M0,0 L10,5 L0,10 Z', fill: 'currentColor' })); defs.appendChild(marker); svg.appendChild(defs);
    var title = input.title || '关联星簇';
    svg.appendChild(node('text', { 'class': 'atlas-local-title', x: cx, y: cy - 12 }, title.length > 14 ? title.slice(0, 13) + '…' : title));
    svg.appendChild(node('text', { 'class': 'atlas-local-hint', x: cx, y: cy + 12 }, input.note || (nodes.length + ' 个已知节点')));
    shown.forEach(function (n, i) {
      var angle = -Math.PI / 2 + 2 * Math.PI * i / Math.max(1, shown.length), x = cx + Math.cos(angle) * radius, y = cy + Math.sin(angle) * radius;
      // A connection is only drawn when its input has an explicit relation label.
      if (n.edge) {
        var startX = n.direction === 'in' ? x : cx, startY = n.direction === 'in' ? y : cy, endX = n.direction === 'in' ? cx : x, endY = n.direction === 'in' ? cy : y;
        var link = node('path', { 'class': 'atlas-local-link', 'data-kind': n.edgeKind || 'member', d: 'M ' + startX + ' ' + startY + ' Q ' + (cx + (x - cx) * .7) + ' ' + cy + ' ' + endX + ' ' + endY });
        if (n.direction) link.setAttribute('marker-end', 'url(#atlas-local-arrow)');
        link.appendChild(node('title', {}, n.edge)); svg.appendChild(link);
      }
      var star = node('g', { 'class': 'atlas-local-node' + (selected != null && String(selected) === String(n.id) ? ' is-selected' : ''), 'data-kind': n.type || 'character', 'data-id': n.id, role: 'button', tabindex: 0, 'aria-label': (n.type || '节点') + ' · ' + n.label, transform: 'translate(' + x + ',' + y + ')' });
      star.setAttribute('aria-pressed', selected != null && String(selected) === String(n.id) ? 'true' : 'false');
      star.setAttribute('data-local-index', String(i));
      if (n.type === 'item') star.appendChild(node('path', { d: 'M0,-10 L10,0 L0,10 L-10,0 Z' }));
      else if (n.type === 'location') star.appendChild(node('path', { d: 'M-8,-8 H8 V8 H-8 Z' }));
      else star.appendChild(node('circle', { r: n.type === 'character' ? 8 : 6 }));
      star.appendChild(node('circle', { r: 22, opacity: 0, 'pointer-events': 'all' }));
      star.appendChild(node('text', { y: 31 }, n.label.length > 10 ? n.label.slice(0, 9) + '…' : n.label));
      if (n.direction) star.appendChild(node('text', { y: -28, 'class': 'atlas-local-hint' }, n.edge));
      star.appendChild(node('title', {}, n.label + (n.edge ? ' · ' + n.edge : '')));
      var choose = function () {
        selected = n.id;
        Array.prototype.forEach.call(svg.querySelectorAll('.atlas-local-node'), function (other) {
          other.classList.remove('is-selected');
          other.setAttribute('aria-pressed', 'false');
        });
        star.classList.add('is-selected');
        star.setAttribute('aria-pressed', 'true');
        if (typeof input.onSelect === 'function') input.onSelect(n);
      };
      star.addEventListener('click', choose);
      star.addEventListener('focus', function () { focusNode = i; });
      star.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); choose(); return; }
        if (!shown.length) return;
        var to = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') to = (i + 1) % shown.length;
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') to = (i - 1 + shown.length) % shown.length;
        else if (e.key === 'Home') to = 0;
        else if (e.key === 'End') to = shown.length - 1;
        if (to == null) return;
        e.preventDefault(); e.stopPropagation(); focusNode = to;
        var next = svg.querySelector('.atlas-local-node[data-local-index="' + to + '"]');
        if (next) next.focus();
      });
      svg.appendChild(star);
    });
    var footer = Math.min(H - bottom + 25, cy + radius + 74);
    var totalPages = Math.max(1, Math.ceil(nodes.length / pageSize));
    var status = node('text', { 'class': 'atlas-local-page-status', x: cx, y: footer - 27, role: 'status', 'aria-live': 'polite' }, totalPages > 1 ? '第 ' + (page + 1) + ' / ' + totalPages + ' 页 · ' + nodes.length + ' 个节点' : nodes.length + ' 个节点');
    svg.appendChild(status);
    button(svg, cx, footer, '收回', close);
    if (nodes.length > pageSize) {
      button(svg, cx - 96, footer, '← ' + (page + 1), function () { page = (page - 1 + totalPages) % totalPages; focusNode = -1; draw(); });
      button(svg, cx + 96, footer, totalPages + ' →', function () { page = (page + 1) % totalPages; focusNode = -1; draw(); });
    }
    host.appendChild(svg);
  }
  function open(spec) {
    close(); input = spec; page = 0; focusNode = -1; host = document.createElement('div'); host.className = 'atlas-local-layer'; host.id = 'atlasLocalGraph'; document.body.appendChild(host); draw();
    document.body.classList.add('atlas-local-open'); return true;
  }
  function close() { if (host) host.remove(); host = null; input = null; selected = null; focusNode = -1; document.body.classList.remove('atlas-local-open'); }
  g.addEventListener('resize', function () { if (host) draw(); });
  g.CLAtlasLocalGraph = { open: open, close: close, isOpen: function () { return !!host; },
    snapshot: function () { return input ? { spec: input, page: page, selected: selected } : null; },
    restore: function (snap) { if (!snap) { close(); return; } open(snap.spec); page = snap.page || 0; selected = snap.selected; draw(); },
    stats: function () { return { on: !!host, page: page, count: input ? (input.nodes || []).length : 0, visible: host ? host.querySelectorAll('.atlas-local-node').length : 0, selected: selected }; } };
})(window);
