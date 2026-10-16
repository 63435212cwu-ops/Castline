(function (g) {
  'use strict';
  var doc = g.document, NS = 'http://www.w3.org/2000/svg';

  function mk(tag, cls, parent, text, owner) {
    var d = owner || (parent && parent.ownerDocument) || doc, e = d.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = String(text);
    if (parent) parent.appendChild(e);
    return e;
  }
  function svg(tag, cls, parent, text) {
    var d = (parent && parent.ownerDocument) || doc, e = d.createElementNS(NS, tag);
    if (cls) e.setAttribute('class', cls);
    if (text != null) e.textContent = String(text);
    if (parent) parent.appendChild(e);
    return e;
  }
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function nowMs(fallback) { return g.performance && g.performance.now ? g.performance.now() : fallback != null ? fallback : Date.now(); }
  function now() { return nowMs() / 1000; }
  function mediaReduced() {
    try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function reduced() {
    var T = g.CLSkyTokens;
    return T && T.reduced ? !!T.reduced() : mediaReduced();
  }
  function rgb(hex, out) {
    out = out || [0, 0, 0];
    out[0] = ((hex >> 16) & 255) / 255; out[1] = ((hex >> 8) & 255) / 255; out[2] = (hex & 255) / 255;
    return out;
  }
  function num(n) { n = Math.round(+n || 0); return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function chars(t) { return String(t == null ? '' : t).match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[\s\S]/g) || []; }

  function spring(s, to, w, z, dt) {
    var a = -w * w * (s.x - to) - 2 * z * w * s.v;
    s.v += a * dt; s.x += s.v * dt;
    return s;
  }

  function type(el, text, o) {
    o = o || {};
    var list = chars(text), cps = o.cps || 12.5, d0 = o.delay || 0, i, s;
    el.textContent = '';
    el.classList.remove('is-glint', 'has-caret', 'is-typed');
    if (reduced() || o.instant) {
      el.textContent = String(text == null ? '' : text);
      el.classList.add('is-typed');
      if (o.caret) el.classList.add('has-caret');
      return 0;
    }
    el.classList.add('skd-type');
    if (o.cls) el.classList.add(o.cls);
    var tt = d0 + list.length / cps;
    el.style.setProperty('--type-dt', (1 / cps).toFixed(4) + 's');
    el.style.setProperty('--type-d0', d0.toFixed(3) + 's');
    el.style.setProperty('--type-tt', tt.toFixed(3) + 's');
    var frag = doc.createDocumentFragment();
    for (i = 0; i < list.length; i++) {
      s = doc.createElement('span');
      s.className = 'skd-type__c';
      s.style.setProperty('--i', String(i));
      s.textContent = list[i];
      frag.appendChild(s);
    }
    el.appendChild(frag);
    if (o.glint) el.classList.add('is-glint');
    if (o.caret) el.classList.add('has-caret');
    return tt;
  }

  g.CLSkyUtil = { mk: mk, svg: svg, esc: esc, clamp: clamp, now: now, nowMs: nowMs, mediaReduced: mediaReduced, reduced: reduced, rgb: rgb, num: num, chars: chars, spring: spring, type: type };
})(window);
