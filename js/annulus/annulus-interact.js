/**
 * @role micro
 * @owns js/annulus/annulus-interact.js
 * @budget dom +1（悬停卡）· 无逐帧 · drawcalls 0
 * @contract v80
 * 年轮交互（主控自写：传送带三次未过门禁，按 forge 纪律由主控接手）。
 * 事件委托挂在 .cl-ann-layer：只响应 .is-hit（弧 / 弧头 / 权杖结 / 名册珠）。
 * DOM 约定与 svg/marks 一致：.cl-ann-arc|.cl-ann-head[data-id] · .cl-ann-handoff[data-from][data-to] ·
 * .cl-ann-bead[data-name][data-id]。卡片坐标只写 transform（与 js/hud/tooltip.js 同法）。
 * 降级：prefers-reduced-motion / CLOrbit3DTier low / hardwareConcurrency<=4 → 卡片 is-reduced（CSS 关过渡）。
 */
(function (g) {
  'use strict';
  var doc = g.document;
  var layer = null, card = null, view = null, A = null;
  var hover = null, focus = null, cardOn = false, bound = [], vOff = null;

  function add(el, t, fn) { if (el && el.addEventListener) { el.addEventListener(t, fn, false); bound.push([el, t, fn]); } }
  function call(o, m, a) { if (o && typeof o[m] === 'function') { try { return o[m](a); } catch (e) {} } }
  function sid(v) { return (v === undefined || v === null || v === '') ? null : String(v); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function reduced() {
    try { if (g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches) return true; } catch (e) {}
    try { if (g.CLOrbit3DTier && g.CLOrbit3DTier.get() === 'low') return true; } catch (e2) {}
    return !!(g.navigator && g.navigator.hardwareConcurrency <= 4);
  }
  function cls(n) { return ' ' + ((n && n.getAttribute && n.getAttribute('class')) || '') + ' '; }
  function has(n, c) { return cls(n).indexOf(' ' + c + ' ') >= 0; }
  function hitOf(t) {
    var n = t;
    while (n && n !== layer && n !== doc) { if (n.nodeType === 1 && has(n, 'is-hit')) return n; n = n.parentNode; }
    return null;
  }
  function kindOf(n) {
    if (has(n, 'cl-ann-bead')) return 'bead';
    if (has(n, 'cl-ann-handoff')) return 'handoff';
    return 'line';
  }
  function ringById(id) {
    if (!A || !A.rings || id == null) return null;
    for (var i = 0; i < A.rings.length; i++) if (String(A.rings[i].id) === String(id)) return A.rings[i];
    return null;
  }
  function shortOf(id) { var r = ringById(id); return r ? (r.shortName || r.name || String(id)) : String(id == null ? '' : id); }
  function handoffOf(from, to) {
    var hs = (A && A.handoffs) || [], i;
    for (i = 0; i < hs.length; i++) if (String(hs[i].fromId) === String(from) && String(hs[i].toId) === String(to)) return hs[i];
    return null;
  }
  var LIFE = { active: '活跃中', resolved: '已收束', suspended: '悬置', open: '未定', unknown: '状态未知' };
  var KIND = { main: '主线', branch: '支线', twig: '细枝' };
  function lineHTML(r) {
    var h = '<div class="cl-ann-card__title">' + esc(r.shortName || r.name || r.id) + '</div>';
    var badge = (KIND[r.kind] || r.kind || '') + (r.gen != null ? ' · 第 ' + (r.gen + 1) + ' 代' : '') + ' · ' + (LIFE[r.lifecycle] || LIFE.unknown);
    h += '<div class="cl-ann-card__meta">' + esc(badge) + '</div>';
    var m = (r.eventCount || 0) + ' 事', cs = r.chapSpan;
    if (cs && cs.known && cs.first != null && cs.last != null && cs.last >= cs.first) m += ' · 跨 ' + (cs.last - cs.first + 1) + ' 章';
    if (r.lengthRank != null) m += ' · 长度 #' + r.lengthRank;
    h += '<div class="cl-ann-card__meta">' + esc(m) + '</div>';
    var lead = (r.roster && r.roster.lead) || r.lead || '', core = (r.roster && r.roster.core) || [], bits = [];
    if (lead) bits.push('领衔 ' + lead);
    if (core.length) bits.push('核心 ' + core.slice(0, 3).join(' · '));
    if (r.roster && r.roster.more > 0) bits.push('等 ' + r.roster.more + ' 人');
    if (bits.length) h += '<div class="cl-ann-card__cast">' + esc(bits.join(' · ')) + '</div>';
    return h;
  }
  function handoffHTML(from, to) {
    var h = handoffOf(from, to);
    return '<div class="cl-ann-card__title">' + esc(shortOf(from)) + ' → ' + esc(shortOf(to)) + '</div>' +
      '<div class="cl-ann-card__meta">主线更替 · ' + esc(h && h.known && h.reason ? h.reason : '理由未知') + '</div>';
  }
  function inAvoid(l, t, w, h, W, H) {
    function ov(a, b, c, d) { return l < a + c && l + w > a && t < b + d && t + h > b; }
    return ov(0, 0, 400, 330) || ov(0, 320, 215, 420) || ov(W * 0.22, H - 150, W * 0.56, 150) || l < 0 || t < 0 || l + w > W || t + h > H;
  }
  function place(x, y) {
    if (!card || !cardOn) return;
    var w = card.offsetWidth || 160, h = card.offsetHeight || 48, W = g.innerWidth, H = g.innerHeight, gap = 14;
    var o = [{ c: 'is-right', l: x + gap, t: y + gap }, { c: 'is-left', l: x - gap - w, t: y + gap },
             { c: 'is-right is-up', l: x + gap, t: y - gap - h }, { c: 'is-left is-up', l: x - gap - w, t: y - gap - h }], pick = o[0], i;
    for (i = 0; i < o.length; i++) if (!inAvoid(o[i].l, o[i].t, w, h, W, H)) { pick = o[i]; break; }
    card.className = 'cl-ann-card is-on ' + (reduced() ? 'is-reduced ' : '') + pick.c;
    card.style.transform = 'translate(' + Math.round(Math.max(0, Math.min(pick.l, W - w))) + 'px,' + Math.round(Math.max(0, Math.min(pick.t, H - h))) + 'px)';
  }
  function showCard(html, ev) { if (!card) return; card.innerHTML = html; cardOn = true; place(ev.clientX, ev.clientY); }
  function hideCard() { cardOn = false; if (card) { card.className = 'cl-ann-card'; card.style.transform = ''; } }

  function setHover(id) { hover = sid(id); call(g.CLAnnulusSVG, 'setHover', hover); call(g.CLAnnulusLedger, 'setHover', hover); }
  function setFocus(id) { focus = sid(id); call(g.CLAnnulusSVG, 'setFocus', focus); call(g.CLAnnulusLedger, 'setFocus', focus); }
  function emit(type, detail) { try { doc.dispatchEvent(new CustomEvent(type, { detail: detail })); } catch (e) {} }
  function focusLine(id) {
    setFocus(id);
    if (view && typeof view.focusThread === 'function') { try { view.focusThread(id); } catch (e) {} }
    emit('cl:plot-thread', { id: id });
  }

  function onOver(ev) {
    var hit = hitOf(ev.target); if (!hit) return;
    var k = kindOf(hit), id = hit.getAttribute('data-id');
    if (k === 'bead') { setHover(id); hideCard(); return; }
    if (k === 'handoff') { setHover(hit.getAttribute('data-to')); showCard(handoffHTML(hit.getAttribute('data-from'), hit.getAttribute('data-to')), ev); return; }
    setHover(id);
    var r = ringById(id);
    if (r) showCard(lineHTML(r), ev); else hideCard();
  }
  function onOut(ev) {
    var to = ev.relatedTarget;
    if (to && layer && layer.contains(to) && hitOf(to)) return;
    setHover(null); hideCard();
  }
  function onMove(ev) { if (cardOn) place(ev.clientX, ev.clientY); }
  function onClick(ev) {
    var hit = hitOf(ev.target); if (!hit) return;
    var k = kindOf(hit), id = hit.getAttribute('data-id');
    if (k === 'bead') { var nm = hit.getAttribute('data-name'); if (nm) emit('cl:plot-char', { name: nm }); return; }
    if (k === 'handoff') { focusLine(sid(hit.getAttribute('data-to'))); return; }
    if (id == null) return;
    focusLine(focus !== null && focus === String(id) ? null : String(id));
    if (focus === null) hideCard();
  }
  /* W1.5：点空处清焦——层本身 pointer-events:none，空处点击落在 WebGL 画布/body 上，故在 document 级监听 */
  function onDocClick(ev) {
    if (focus === null) return;
    var t = ev.target;
    if (!t) return;
    if (layer && layer.contains(t)) { if (!hitOf(t)) focusLine(null); return; }
    var tag = (t.tagName || '').toUpperCase();
    if (tag === 'CANVAS' || t === doc.body || t === doc.documentElement) { setHover(null); hideCard(); focusLine(null); }
  }
  function onKey(ev) {
    if (!ev || (ev.key !== 'Escape' && ev.key !== 'Esc' && ev.keyCode !== 27)) return;
    setHover(null); hideCard();
    if (focus !== null) focusLine(null);
  }
  function onLedgerHover(ev) { setHover(ev && ev.detail ? ev.detail.id : null); hideCard(); }
  function onLedgerClick(ev) {
    var id = sid(ev && ev.detail ? ev.detail.id : null);
    if (id !== null && focus === id) return;
    setFocus(id);
    if (view && typeof view.focusThread === 'function') { try { view.focusThread(id); } catch (e) {} }
  }
  function onThread(id) { setFocus(id); }

  function attach(v, model) {
    detach();
    view = v || null; A = model || null;
    layer = doc.querySelector('.cl-ann-layer');
    if (!layer) return false;
    card = doc.createElement('div'); card.className = 'cl-ann-card'; layer.appendChild(card);
    add(layer, 'pointerover', onOver); add(layer, 'pointerout', onOut); add(layer, 'pointermove', onMove); add(layer, 'click', onClick);
    add(doc, 'keydown', onKey); add(doc, 'click', onDocClick); add(doc, 'cl:ann-ledger-hover', onLedgerHover); add(doc, 'cl:ann-ledger-click', onLedgerClick);
    if (view && typeof view.on === 'function') {
      var off = view.on('thread', onThread);
      vOff = (typeof off === 'function') ? off : (typeof view.off === 'function' ? function () { view.off('thread', onThread); } : null);
      try { var st = view.state ? view.state() : null; if (st && st.thread != null) setFocus(st.thread); } catch (e) {}
    }
    return true;
  }
  function detach() {
    for (var i = 0; i < bound.length; i++) bound[i][0].removeEventListener(bound[i][1], bound[i][2], false);
    bound = [];
    if (vOff) { try { vOff(); } catch (e) {} vOff = null; }
    if (card && card.parentNode) card.parentNode.removeChild(card);
    card = null; layer = null; view = null; A = null; hover = null; focus = null; cardOn = false;
  }
  g.CLAnnulusInteract = { name: 'annulus-interact', version: 'v80', attach: attach, detach: detach,
    stats: function () { return { hover: hover, focus: focus, cardOn: cardOn }; } };
})(window);
