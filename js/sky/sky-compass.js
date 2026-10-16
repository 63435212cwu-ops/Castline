(function (g) {
  'use strict';
  var doc = document;
  var MAX_SAT = 12, KEY_KINDS = /转折|高燃|抉择|冲突|高潮|揭秘/;
  var REL_ORDER = ['ally', 'kin', 'bond', 'oppose', 'dark', 'other', 'cooccur'];
  var REL_FALLBACK = { ally: '合作', kin: '亲缘', bond: '情感', oppose: '对立', dark: '暗线', other: '其他', cooccur: '同场 · 推导' };
  var svg = null, note = null, st = null, opts = null, lastKey = '', tick = 0;

  var mk = g.CLSkyUtil.svg, clamp = g.CLSkyUtil.clamp, esc = g.CLSkyUtil.esc;
  function f1(v) { return v.toFixed(1); }
  function attrs(el, o) { for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) el.setAttribute(k, typeof o[k] === 'number' ? f1(o[k]) : o[k]); }
  function show(el, on) { if (el) el.setAttribute('visibility', on ? 'visible' : 'hidden'); }
  function relLabel(id) {
    var M = g.CLDomainsModel, list = M && M.REL_CLASSES || [];
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i].label;
    return REL_FALLBACK[id] || '联系';
  }
  function relRank(id) { var i = REL_ORDER.indexOf(id); return i < 0 ? REL_ORDER.length : i; }
  var RING_OF = { ally: 0, kin: 0, bond: 0, oppose: 1, dark: 1 }, RING_NAME = ['亲近', '对抗', '其他'], RING_Q = [5, 4, 3];
  function ringOf(id) { return RING_OF[id] != null ? RING_OF[id] : 2; }
  function pickSats(rels, max) {
    if (rels.length <= max) return rels.slice();
    var by = [[], [], []], took = [0, 0, 0], out = [], r;
    rels.forEach(function (x) { by[ringOf(x.cls)].push(x); });
    for (r = 0; r < 3; r++) { took[r] = Math.min(RING_Q[r], by[r].length); out = out.concat(by[r].slice(0, took[r])); }
    while (out.length < max) {
      var best = -1;
      for (r = 0; r < 3; r++) if (took[r] < by[r].length && (best < 0 || by[r][took[r]].strength > by[best][took[best]].strength)) best = r;
      if (best < 0) break;
      out.push(by[best][took[best]++]);
    }
    return out.sort(function (a, b) { return rels.indexOf(a) - rels.indexOf(b); });
  }
  var fontOf = {}, fontVw = 0, mctx = null;
  function fontFor(el) {
    var vw = g.innerWidth || 0, cls = (el.getAttribute('class') || '').split(' ')[0];
    if (vw !== fontVw) { fontOf = {}; fontVw = vw; }
    var f = fontOf[cls];
    if (!f) {
      var cs = g.getComputedStyle(el), ls = parseFloat(cs.letterSpacing);
      f = fontOf[cls] = { font: [cs.fontStyle, cs.fontWeight, cs.fontSize, cs.fontFamily].join(' '), ls: isFinite(ls) ? ls : 0 };
    }
    return f;
  }
  function txtW(el, px) {
    if (!el) return 0;
    var t = el.textContent || '';
    if (el._wt !== t || !(el._w > 0)) {
      var w = 0;
      try {
        if (!mctx) mctx = doc.createElement('canvas').getContext('2d');
        var f = fontFor(el); mctx.font = f.font;
        w = t ? mctx.measureText(t).width + f.ls * t.length : 0;
      } catch (e) { w = 0; }
      el._w = w > 0 ? w : t.length * (px || 12); el._wt = t;
    }
    return el._w;
  }
  function short(t, n) { t = String(t || ''); return t.length > n ? t.slice(0, n) + '…' : t; }

  function relationsOf(name, view, G) {
    var M = g.CLDomainsModel, list = [], seen = {};
    (view.relations || []).forEach(function (r) {
      if (r.a !== name && r.b !== name) return;
      var other = r.a === name ? r.b : r.a; if (!other || other === name) return;
      var cls = M && M.relClass ? M.relClass(r) : { id: 'other', label: '联系', dash: 0 };
      var key = other + '|' + cls.id; if (seen[key]) { seen[key].strength = Math.max(seen[key].strength, r.strength || 0); return; }
      var o = { name: other, kind: r.kind || cls.label, cls: cls.id, clsLabel: cls.label, dash: cls.dash || 0, strength: r.derived ? (r.n || 1) / 20 + 0.3 : (isFinite(r.strength) ? r.strength : 0.5), derived: !!r.derived, n: r.n || 0, desc: r.desc || '' };
      seen[key] = o; list.push(o);
    });
    var imp = {}; G.characters.forEach(function (c) { imp[c.name] = c.importance || 0; });
    list.sort(function (a, b) { return b.strength - a.strength || (imp[b.name] || 0) - (imp[a.name] || 0); });
    return list;
  }
  function chapterLabel(c, M) {
    if (g.CLSkyModel && g.CLSkyModel.chapterLabel) return g.CLSkyModel.chapterLabel(M, c);
    var ch = M.chapters && M.chapters[c], axis = M.axis || {};
    if (!ch) return '未分章';
    if (ch.special || ch.no == null || axis.mode === 'seq') return ch.name || '未分章';
    return '第 ' + ch.no + ' ' + (axis.unit || '回');
  }
  function eventsOf(name, G, M, ctx) {
    var chIdx = {}; (M.chapters || []).forEach(function (c) { chIdx[c.name] = c.idx; });
    var eventCh = {}; (M.chapterEvents || []).forEach(function (indices, c) { indices.forEach(function (i) { eventCh[i] = c; }); });
    var out = [], Bd = g.CLSkyCompassBand;
    G.events.forEach(function (e, i) { if ((e.characters || []).indexOf(name) >= 0) out.push({ i: i, e: e, c: eventCh[i] != null ? eventCh[i] : chIdx[e.chapter] != null ? chIdx[e.chapter] : 0, key: KEY_KINDS.test(e.kind || ''), sc: ctx && Bd ? Bd.eventScore(e, i, ctx) : 0 }); });
    out.sort(function (a, b) { return a.c - b.c || (a.e.order || 0) - (b.e.order || 0); });
    var byC = {}, list = [];
    out.forEach(function (o) { var b = byC[o.c]; if (!b) { b = byC[o.c] = { c: o.c, items: [] }; list.push(b); } b.items.push(o); });
    return list.map(function (b) {
      var keys = b.items.filter(function (x) { return x.key; }), rep = keys[0] || b.items[0], top = b.items[0];
      b.items.forEach(function (x) { if (x.sc > top.sc) top = x; });
      if (ctx) rep = top;
      var cast = []; b.items.forEach(function (x) { (x.e.characters || []).forEach(function (n) { if (cast.indexOf(n) < 0) cast.push(n); }); });
      var titles = b.items.map(function (x) { return (x.key ? '◆ ' : '') + (x.e.title || ''); }).filter(Boolean);
      return { i: rep.i, c: b.c, no: M.chapters && M.chapters[b.c] ? M.chapters[b.c].no : null, chapter: chapterLabel(b.c, M), key: keys.length > 0, keyCount: keys.length, count: b.items.length,
        imp: top.sc + 0.05 * Math.log(b.items.length), ids: b.items.map(function (x) { return x.i; }),
        list: b.items.map(function (x) { return { t: x.e.title || '', key: x.key, kind: x.e.kind || '' }; }),
        e: { title: rep.e.title, kind: rep.e.kind, summary: b.items.length > 1 ? titles.slice(0, 5).join(' · ') + (titles.length > 5 ? ' …' : '') : rep.e.summary, characters: cast } };
    });
  }

  function ensureSvg() {
    if (svg) return svg;
    svg = mk('svg', 'sky-compass'); svg.setAttribute('aria-label', '罗盘：关系与人物事件链');
    var defs = mk('defs', null, svg), mkr = mk('marker', null, defs);
    attrs(mkr, { id: 'skcArrow', viewBox: '0 0 8 8', refX: '6', refY: '4', markerWidth: '6', markerHeight: '6', orient: 'auto' });
    mk('path', 'skc-arrow', mkr).setAttribute('d', 'M1 1 7 4 1 7');
    var mkc = mk('marker', null, defs);
    attrs(mkc, { id: 'skcCause', viewBox: '0 0 8 8', refX: '6.5', refY: '4', markerWidth: '5', markerHeight: '5', orient: 'auto' });
    mk('path', 'skc-cause-tip', mkc).setAttribute('d', 'M1 1.2 7 4 1 6.8z');
    var mask = mk('mask', null, defs); attrs(mask, { id: 'skcKnock', maskUnits: 'userSpaceOnUse' });
    svg.mask = mask; svg.maskBg = mk('rect', 'skc-mask-show', mask); svg.maskHoles = mk('g', 'skc-mask-hole', mask);
    svg.gOrbit = mk('g', 'skc-orbit', svg); svg.gLinks = mk('g', 'skc-links', svg); svg.gLinks.setAttribute('mask', 'url(#skcKnock)');
    svg.gCause = mk('g', 'skc-causes', svg);
    svg.gChain = mk('g', 'skc-chain', svg); svg.gChainLab = mk('g', 'skc-chain-labels', svg); svg.gSat = mk('g', 'skc-sats', svg);
    svg.card = doc.createElement('div'); svg.card.className = 'sky-card skc-card'; svg.card.hidden = true;
    note = doc.createElement('div'); note.className = 'sky-legend skc-note'; note.setAttribute('role', 'note'); note.hidden = true;
    doc.body.appendChild(svg); doc.body.appendChild(svg.card); doc.body.appendChild(note);
    svg.addEventListener('pointerover', onOver); svg.addEventListener('pointerout', onOut); svg.addEventListener('click', onClick);
    svg.addEventListener('pointermove', onBandMove); svg.addEventListener('pointerout', onBandOut);
    var hk = { state: function () { return st; }, txtW: txtW, unlight: function () { unlight(); },
      lightEvent: function (k) { if (st && st.dots[k]) lightEvent(k); }, lightSat: function (i) { if (st && st.sats[i]) lightSat(i); },
      scene: function () { return opts && opts.scene; }, pick: function (name) { if (opts && opts.onPick) opts.onPick(name); } };
    if (g.CLSkyCompassDrag) CLSkyCompassDrag.attach(svg, hk);
    if (g.CLSkyCompassFan) CLSkyCompassFan.attach(svg, hk);
    return svg;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function resetMods() { if (g.CLSkyCompassDrag) CLSkyCompassDrag.reset(); if (g.CLSkyCompassFan) CLSkyCompassFan.reset(); }

  function open(name, o) {
    opts = o || {}; ensureSvg(); resetMods();
    var G = opts.graph, M = opts.model, view = opts.view || G;
    if (!G || !M) return;
    var Bd = g.CLSkyCompassBand, ctx = Bd && Bd.context ? Bd.context(name, G, view) : null;
    var rels = relationsOf(name, view, G), evs = eventsOf(name, G, M, ctx), pick = pickSats(rels, MAX_SAT);
    st = { name: name, rels: pick, more: Math.max(0, rels.length - pick.length), total: rels.length, evs: evs, sats: [], dots: [], hover: null, env: null, noteKey: '' };
    [svg.gOrbit, svg.gLinks, svg.gCause, svg.gChain, svg.gChainLab, svg.gSat, svg.maskHoles].forEach(clear);
    var beadOf = {}; evs.forEach(function (b, k) { (b.ids || []).forEach(function (i) { beadOf[i] = k; }); });
    st.cause = ctx && Bd.causeLinks ? Bd.causeLinks(ctx, beadOf) : { arcs: [], self: {} };
    st.cause.arcs.forEach(function (a, j) {
      a.el = mk('path', 'skc-cause', svg.gCause); a.el.setAttribute('marker-end', 'url(#skcCause)');
      a.hit = mk('path', 'skc-cause-hit', svg.gCause); a.hit.setAttribute('data-cause', String(j));
    });
    st.causeSelf = Object.keys(st.cause.self).map(function (k) { var c = mk('circle', 'skc-cause-self', svg.gCause); return { k: +k, el: c, list: st.cause.self[k] }; });
    st.nCause = st.cause.arcs.length + st.causeSelf.reduce(function (t, x) { return t + x.list.length; }, 0);
    st.grpLab = RING_NAME.map(function (t) { var e = mk('text', 'skc-grp', svg.gSat); e.textContent = t; show(e, false); return e; });
    st.arcs = [mk('path', 'skc-ring', svg.gOrbit), mk('path', 'skc-ring', svg.gOrbit)];
    var sMax = 0; st.rels.forEach(function (r) { sMax = Math.max(sMax, r.strength || 0); });
    st.rels.forEach(function (r, i) {
      var link = mk('path', 'skc-link r-' + r.cls + (r.derived ? ' is-derived' : ''), svg.gLinks);
      var gS = mk('g', 'skc-sat r-' + r.cls, svg.gSat); gS.setAttribute('data-sat', String(i)); gS.setAttribute('tabindex', '0'); gS.setAttribute('role', 'button');
      gS.setAttribute('aria-label', r.name + ' · ' + (r.derived ? '同场 ' + r.n + ' 次（推导）' : r.kind) + ' · 进入其罗盘');
      mk('circle', 'skc-sat-hit', gS).setAttribute('r', '16');
      var rr = 2.4 + 2.2 * (sMax > 0 ? clamp((r.strength || 0) / sMax, 0, 1) : 0.5);
      var dot = mk('circle', 'skc-sat-star', gS); dot.setAttribute('r', f1(rr));
      var nm = mk('text', 'skc-sat-name', gS); nm.textContent = r.name;
      var kd = mk('text', 'skc-sat-kind', gS); kd.textContent = r.derived ? '同场 ' + r.n : r.kind;
      st.sats.push({ r: r, g: gS, link: link, name: nm, kind: kd, rr: rr, shown: true });
    });
    st.ord = st.sats.map(function (s, i) { return i; }).sort(function (a, b) { return ringOf(st.sats[a].r.cls) - ringOf(st.sats[b].r.cls) || a - b; });
    st.chain = mk('path', 'skc-chain-line', svg.gChain);
    st.flowG = mk('path', 'skc-flow is-glow', svg.gChain); st.flow = mk('path', 'skc-flow', svg.gChain);
    st.flowG.setAttribute('pathLength', '1'); st.flow.setAttribute('pathLength', '1');
    st.steps = [];
    var maxC = 1; evs.forEach(function (x) { maxC = Math.max(maxC, x.count || 1); }); st.maxC = maxC;
    st.gSteps = mk('g', 'skc-steps', svg.gChain);
    st.bandAll = mk('path', 'skc-band', svg.gChain); st.bandKey = mk('path', 'skc-band is-key', svg.gChain); st.bandSel = mk('path', 'skc-band is-sel', svg.gChain);
    st.bandHit = mk('path', 'skc-band-hit', svg.gChain); st.bandHit.setAttribute('data-band', '1');
    st.bandCur = mk('circle', 'skc-band-cur', svg.gChain); show(st.bandCur, false);
    st.gDots = mk('g', 'skc-dots', svg.gChain);
    evs.forEach(function (x) { st.dots.push({ o: x, el: null, lab: null }); });
    st.chNo0 = mk('text', 'skc-ch is-start', svg.gChainLab); st.chNo1 = mk('text', 'skc-ch is-end', svg.gChainLab);
    if (evs.length) { st.chNo0.textContent = short(evs[0].chapter, 14); st.chNo1.textContent = short(evs[evs.length - 1].chapter, 14); }
    var nEv = evs.reduce(function (t, x) { return t + (x.count || 1); }, 0);
    st.nEv = nEv;
    st.rule0 = mk('path', 'skc-rule', svg.gChainLab); st.rule1 = mk('path', 'skc-rule', svg.gChainLab); st.rule1.setAttribute('marker-end', 'url(#skcArrow)');
    st.chainTitle = mk('text', 'skc-chain-title', svg.gChainLab);
    st.chainTitle.textContent = evs.length ? '人物事件链 · ' + nEv + ' 事件 · ' + evs.length + ' 个章节段' : '人物事件链 · 暂无事件记录';
    crumbTitle(name, G);
    svg.classList.add('is-on'); note.hidden = false; lastKey = ''; tick = 0;
    st.sats.forEach(function (s) { txtW(s.name, 12); txtW(s.kind, 10); });
    st.grpLab.forEach(function (e) { txtW(e, 10); });
    txtW(st.chNo0, 10); txtW(st.chNo1, 10); txtW(st.chainTitle, 10);
    st.dirty = true;
  }
  function close() {
    if (!svg) return;
    resetMods();
    svg.classList.remove('is-on'); svg.card.hidden = true; if (note) { note.hidden = true; note.innerHTML = ''; }
    [svg.gOrbit, svg.gLinks, svg.gCause, svg.gChain, svg.gChainLab, svg.gSat, svg.maskHoles].forEach(clear);
    if (g.CLSkyOrrery && CLSkyOrrery.setTextMask) CLSkyOrrery.setTextMask(null);
    var cr = doc.getElementById('skyCrumb'); if (cr) { cr.style.removeProperty('--skc-crumb-top'); cr.style.removeProperty('--skc-crumb-r'); }
    st = null;
  }
  function crumbTitle(name, G) {
    var meta = doc.getElementById('skyCrumbMeta'); if (!meta) return;
    var ch = (G.characters || []).filter(function (c) { return c.name === name; })[0] || {};
    var evN = G.events.filter(function (e) { return (e.characters || []).indexOf(name) >= 0; }).length;
    meta.setAttribute('title', [ch.camp, ch.role, ch.stance, evN + ' 事件', ch.identity].filter(function (x) { return x != null && String(x).trim() !== ''; }).join(' · '));
  }

  function rectOf(el) { var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 ? [r.left, r.top, r.right, r.bottom] : null; }
  function shown(el) { if (!el) return false; var cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden'; }
  function readEnv() {
    var labs = [], lel = [], lsig = [], u = null;
    Array.prototype.forEach.call(doc.querySelectorAll('#labels .cl-lab.attr.on, #labels .cl-lab.meta.on'), function (el) {
      if (!shown(el)) return; var b = rectOf(el); if (!b) return;
      labs.push(b); lel.push(el); lsig.push(Math.round(b[0] / 2), Math.round(b[1] / 2), Math.round(b[2] / 2));
      u = u ? [Math.min(u[0], b[0]), Math.min(u[1], b[1]), Math.max(u[2], b[2]), Math.max(u[3], b[3])] : b.slice();
    });
    var tb = doc.querySelector('.sky-top'), tr = shown(tb) ? rectOf(tb) : null, hudTop = tr ? tr[3] : 56;
    var crumb = doc.getElementById('skyCrumb');
    if (crumb && !crumb.hidden) {
      var want = Math.round(hudTop + 10) + 'px', ir = Math.round((opts.inset && opts.inset.right) || 0) + 'px';
      if (crumb.style.getPropertyValue('--skc-crumb-top') !== want) crumb.style.setProperty('--skc-crumb-top', want);
      if (crumb.style.getPropertyValue('--skc-crumb-r') !== ir) crumb.style.setProperty('--skc-crumb-r', ir);
      Array.prototype.forEach.call(crumb.children, function (c) { if (!shown(c)) return; var b = rectOf(c); if (b) hudTop = Math.max(hudTop, b[3]); });
    }
    var hud = [], hudBottom = g.innerHeight;
    Array.prototype.forEach.call(doc.querySelectorAll('.sky-bottom > *:not([hidden]), .sky-lab:not([hidden])'), function (el) {
      if (!shown(el)) return; var b = rectOf(el); if (!b) return;
      hud.push(b); if (b[1] > g.innerHeight * 0.6 && b[3] - b[1] > 6) hudBottom = Math.min(hudBottom, b[1]);
    });
    var S = opts.scene, gl = false; try { gl = !!(S && S.gemLegend && S.gemLegend().on); } catch (e) { gl = false; }
    return { labs: labs, lel: lel, lu: u, hud: hud, hudTop: hudTop, hudBottom: hudBottom, gl: gl, hsig: [Math.round(hudTop), Math.round(hudBottom), gl ? 1 : 0, hud.length].join(','), lsig: lsig.join(',') };
  }
  function knockout(labs) {
    clear(svg.maskHoles);
    if (st.mode !== 'orbit') return;
    labs.forEach(function (b) { attrs(mk('rect', null, svg.maskHoles), { x: b[0] - 6, y: b[1] - 3, width: b[2] - b[0] + 12, height: b[3] - b[1] + 6, rx: 3 }); });
  }
  function grow(k, b) {
    var e = st[k]; if (!e) { st[k] = b.slice(); return true; }
    if (!(b[0] < e[0] - 3 || b[1] < e[1] - 3 || b[2] > e[2] + 3 || b[3] > e[3] + 3)) return false;
    e[0] = Math.min(e[0], b[0]); e[1] = Math.min(e[1], b[1]); e[2] = Math.max(e[2], b[2]); e[3] = Math.max(e[3], b[3]); return true;
  }
  function sweep(el, b) {
    var L = st.labSw || (st.labSw = []), e = null, i;
    for (i = 0; i < L.length; i++) if (L[i].el === el) { e = L[i]; break; }
    if (!e) { L.push({ el: el, b: b.slice() }); return false; }
    var o = e.b;
    if (b[0] > o[2] + 40 || b[2] < o[0] - 40 || b[1] > o[3] + 40 || b[3] < o[1] - 40) { e.b = b.slice(); return false; }
    if (!(b[0] < o[0] - 3 || b[1] < o[1] - 3 || b[2] > o[2] + 3 || b[3] > o[3] + 3)) return false;
    o[0] = Math.min(o[0], b[0]); o[1] = Math.min(o[1], b[1]); o[2] = Math.max(o[2], b[2]); o[3] = Math.max(o[3], b[3]); return true;
  }
  function bounds() {
    var ins = opts.inset || { right: 0, bottom: 0 }, W = g.innerWidth - (ins.right || 0), H = g.innerHeight - (ins.bottom || 0), c = st.envC;
    if (!c) return { W: W, H: H, cx: W / 2, cy: H * 0.45, cw: 240, chh: 300 };
    return { W: W, H: H, cx: (c[0] + c[2]) / 2, cy: (c[1] + c[3]) / 2, cw: c[2] - c[0], chh: c[3] - c[1] };
  }
  function hitAny(b, list, pad) { pad = pad || 0; for (var i = 0; i < list.length; i++) { var o = list[i]; if (b[0] < o[2] + pad && b[2] > o[0] - pad && b[1] < o[3] + pad && b[3] > o[1] - pad) return true; } return false; }

  function frame() {
    if (!st || !svg) return;
    tick++;
    var ins = opts.inset || {}, vk = [g.innerWidth, g.innerHeight, ins.right || 0, ins.bottom || 0].join(','), grew = false;
    if (vk !== lastKey) { lastKey = vk; st.envC = st.envU = null; st.labSw = null; st.env = null; st.noteCheck = true; }
    if (!st.envC || tick % 3 === 0) {
      var S = opts.scene, cb = S && S.crownScreenBounds ? S.crownScreenBounds() : null;
      if (cb && isFinite(cb.left) && cb.right > cb.left) grew = grow('envC', [cb.left, cb.top, cb.right, cb.bottom]);
    }
    if (!st.env || tick % 6 === 0) {
      var env = readEnv(vk), prev = st.env;
      if (env.lu && grow('envU', env.lu)) grew = true;
      for (var li = 0; li < env.labs.length; li++) if (sweep(env.lel[li], env.labs[li])) grew = true;
      env.labsSw = (st.labSw || []).filter(function (e) { return env.lel.indexOf(e.el) >= 0; }).map(function (e) { return e.b; });
      if (!prev || env.hsig !== prev.hsig) grew = true;
      st.env = env;
      if (st.noteCheck && note && !note.hidden) {
        st.noteCheck = false;
        var nh = note.offsetHeight;
        if (nh > (st.noteHt || 16) + 2) { st.noteHt = nh; grew = true; }
      }
      if (!grew && (!prev || env.lsig !== prev.lsig)) knockout(env.labs);
    }
    if (!grew && !st.dirty) return;
    st.dirty = false;
    render(bounds(), st.env);
  }

  function ensureDot(d, k, N) {
    if (d.el) return d.el;
    var c = mk('circle', 'skc-ev' + (d.o.key ? ' is-key' : ''), st.gDots);
    c.setAttribute('data-ev', String(k)); c.style.setProperty('--skd-i', (N > 1 ? k / (N - 1) : 0).toFixed(3));
    c.setAttribute('tabindex', '0'); c.setAttribute('role', 'button');
    c.setAttribute('aria-label', d.o.chapter + ' · ' + (d.o.count || 1) + ' 个事件' + (d.o.keyCount ? ' · ' + d.o.keyCount + ' 关键' : '') + ' · 展开事件短名');
    d.el = c; return c;
  }
  function ensureLab(d) {
    if (d.lab) return d.lab;
    d.lab = mk('text', 'skc-ev-label', svg.gChainLab); d.lab.textContent = short(d.o.e.title, 7); show(d.lab, false);
    return d.lab;
  }
  function render(B, E) {
    st.B = B;
    var W = B.W, H = B.H, VW = g.innerWidth, VH = g.innerHeight, cx = B.cx;
    svg.setAttribute('viewBox', '0 0 ' + VW + ' ' + VH);
    attrs(svg.maskBg, { x: 0, y: 0, width: VW, height: VH });
    var core = [B.cx - B.cw / 2, B.cy - B.chh / 2, B.cx + B.cw / 2, B.cy + B.chh / 2], U = st.envU;
    if (U) { core[0] = Math.min(core[0], U[0]); core[1] = Math.min(core[1], U[1]); core[2] = Math.max(core[2], U[2]); core[3] = Math.max(core[3], U[3]); }
    var top = E.hudTop + 16, noteHt = st.noteHt || 16, noteTop = Math.min(H, E.hudBottom) - 18 - noteHt, bottom = noteTop - 12;
    var n = st.sats.length, maxW = 0;
    st.sats.forEach(function (s) { s.w = Math.max(txtW(s.name, 12), txtW(s.kind, 10)); maxW = Math.max(maxW, s.w); });
    var sideNeed = maxW + 34;
    var orbit = n > 0 && core[0] - 18 - sideNeed >= 8 && (W - 8) - (core[2] + 18) >= sideNeed;
    st.mode = orbit ? 'orbit' : 'grid';
    var coreHalf = Math.max(cx - core[0], core[2] - cx), fit = Math.min(cx - 12 - maxW - 16, (W - cx) - 12 - maxW - 16);
    var rxO = Math.max(coreHalf + 44, Math.min(fit, coreHalf + clamp((fit - coreHalf) * 0.45, 60, 190)));

    var N = st.dots.length, tight = W <= 560, endW = tight ? 0 : Math.max(txtW(st.chNo0, 10), txtW(st.chNo1, 10)) + 12;
    var y0 = core[3] + 24, chordMax = Math.max(80, W - 2 * (endW + 22));
    var chordCap = orbit ? Math.max(240, Math.min(chordMax, 2 * rxO * 0.92 - 2 * endW)) : chordMax;
    var chord = N <= 1 ? 0 : Math.min(chordCap, Math.max(core[2] - core[0] + 40, N * 26, 300));
    var sag = clamp(chord * 0.05, 10, 34), titleGap = tight ? 30 : 32, rowH = tight ? 46 : 50, gridPad = tight ? 12 : 20;
    var cols = 0, rows = 0;
    if (!orbit && n) { cols = clamp(Math.floor((W - 24) / Math.max(96, maxW + 22)), 2, 6); rows = Math.ceil(n / cols); }
    function need(r) { var yt = y0 + sag + titleGap - 6; return r ? yt + gridPad + 8 + (r - 1) * rowH + 34 : yt + 4; }
    if (need(rows) > bottom) sag = Math.max(10, sag - (need(rows) - bottom));
    if (need(rows) > bottom) y0 = Math.max(core[3] + 12, y0 - (need(rows) - bottom));
    while (rows > 1 && need(rows) > bottom) rows--;
    if (need(rows) > bottom) y0 = Math.max(B.cy + B.chh * 0.2, y0 - (need(rows) - bottom));
    var x0 = cx - chord / 2, x1 = cx + chord / 2, sp = N > 1 ? chord / (N - 1) : 40;
    st.chainGeo = { x0: x0, x1: x1, y0: y0, sag: sag, cx: cx, chord: chord };
    var rMax = Math.min(clamp(sp * 0.42, 1.8, 6), 2.6 + 1.3 * Math.sqrt(st.maxC)), pts = [];
    function yAt(x) { var u = chord ? (x - cx) / (chord / 2) : 0; return y0 + sag * (1 - u * u); }
    var bh = clamp(chord / 120, 6, 11);
    var band = g.CLSkyCompassBand ? CLSkyCompassBand.layout({ dots: st.dots, x0: x0, x1: x1, y: yAt, hMax: bh, keyMax: bh / 2 }) : null;
    st.band = band;
    st.dots.forEach(function (d, k) {
      var x = band ? band.xOf(d.o.c) : N === 1 ? cx : x0 + sp * k, y = yAt(x), on = !band || !!band.shown[k];
      var r = !on ? 0 : band ? clamp(2.4 + 1.8 * Math.sqrt((d.o.count || 1) / st.maxC), 2.4, 4.2) : Math.max(1.6, rMax * Math.sqrt((d.o.count || 1) / st.maxC));
      d.x = x; d.y = y; d.r = r; pts.push([x, y]);
      if (on) { ensureDot(d, k, N); attrs(d.el, { cx: x, cy: y, r: r }); show(d.el, true); }
      else if (d.el) show(d.el, false);
    });
    var chd = N > 1 ? 'M' + f1(x0) + ' ' + f1(y0) + 'Q' + f1(cx) + ' ' + f1(y0 + 2 * sag) + ' ' + f1(x1) + ' ' + f1(y0) : '';
    st.chain.setAttribute('d', chd); st.flow.setAttribute('d', chd); st.flowG.setAttribute('d', chd);
    st.bandAll.setAttribute('d', band ? band.pathAll : ''); st.bandKey.setAttribute('d', band ? band.pathKey : '');
    st.bandHit.setAttribute('d', band ? chd : ''); st.bandSel.setAttribute('d', ''); show(st.bandCur, false);
    svg.classList.toggle('skc-banded', !!band);
    var wantSteps = !band && N > 1 && sp >= 22;
    if (wantSteps) while (st.steps.length < N - 1) { var sg = mk('path', 'skc-step', st.gSteps); sg.setAttribute('marker-end', 'url(#skcArrow)'); st.steps.push(sg); }
    st.steps.forEach(function (seg, k) {
      var a = st.dots[k], b = st.dots[k + 1]; if (!a || !b) return;
      var dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
      if (!wantSteps || len - a.r - b.r < 12) { seg.setAttribute('d', ''); return; }
      var ux = dx / len, uy = dy / len;
      seg.setAttribute('d', 'M' + f1(a.x + ux * (a.r + 3)) + ' ' + f1(a.y + uy * (a.r + 3)) + 'L' + f1(b.x - ux * (b.r + 4)) + ' ' + f1(b.y - uy * (b.r + 4)));
    });
    var yLow = N ? y0 + sag : y0, yT = yLow + titleGap - 6;
    if (N) {
      var d0 = st.dots[0], dz = st.dots[N - 1];
      st.chNo0.classList.toggle('is-below', tight); st.chNo1.classList.toggle('is-below', tight);
      if (tight) { attrs(st.chNo0, { x: d0.x - d0.r, y: d0.y + d0.r + 13 }); attrs(st.chNo1, { x: dz.x + dz.r, y: dz.y + dz.r + 13 }); }
      else { attrs(st.chNo0, { x: d0.x - d0.r - 8, y: d0.y + 3.5 }); attrs(st.chNo1, { x: dz.x + dz.r + 8, y: dz.y + 3.5 }); }
      show(st.chNo0, true); show(st.chNo1, N > 1);
    } else { show(st.chNo0, false); show(st.chNo1, false); }
    attrs(st.chainTitle, { x: cx, y: yT });
    var tw = txtW(st.chainTitle, 10), ry = yT - 3.5, rl = N > 1 ? x0 : cx - tw / 2 - 60, rr = N > 1 ? x1 : cx + tw / 2 + 60;
    st.ruleBoxes = [];
    if (rr - rl > tw + 48) {
      st.rule0.setAttribute('d', 'M' + f1(rl) + ' ' + f1(ry) + 'H' + f1(cx - tw / 2 - 12));
      st.rule1.setAttribute('d', 'M' + f1(cx + tw / 2 + 12) + ' ' + f1(ry) + 'H' + f1(rr));
      st.ruleBoxes = [[rl, ry - 2, cx - tw / 2 - 12, ry + 2], [cx + tw / 2 + 12, ry - 2, rr, ry + 2]];
    } else { st.rule0.setAttribute('d', ''); st.rule1.setAttribute('d', ''); }

    var satBoxes = [];
    if (orbit) placeOrbit(); else placeGrid();
    knockout(E.labs);
    function placeOrbit() {
      var yTop = top + 16, yBot = Math.max(yTop + 90, y0 - 36);
      var nR = Math.ceil(n / 2), R = st.ord.slice(0, nR), Lf = st.ord.slice(nR).reverse();
      var cyO = (yTop + yBot) / 2, half = Math.max(40, (yBot - yTop) / 2), ryO = half / 0.7;
      st.orb = { cx: cx, cy: cyO, rx: rxO, ry: ryO };
      var colU = {}, colN = {};
      [[st.ord.slice(0, Math.ceil(n / 2)), 'R'], [st.ord.slice(Math.ceil(n / 2)).reverse(), 'L']].forEach(function (p) {
        var u = 0; p[0].forEach(function (i, k) { if (k && ringOf(st.sats[i].r.cls) !== ringOf(st.sats[p[0][k - 1]].r.cls)) u += 0.6; colU[i] = u; u += 1; }); colN[p[1]] = Math.max(0, u - 1);
      });
      function colY(k, m, i, side) { var U = colN[side > 0 ? 'R' : 'L']; if (m === 1 || !(U > 0)) return cyO; var span = Math.min(yBot - yTop, 104 * U); return cyO - span / 2 + span * colU[i] / U; }
      function ex(y) { var t = (y - cyO) / ryO; return rxO * Math.sqrt(Math.max(0, 1 - t * t)); }
      var obs = E.labs.concat(E.hud);
      [[R, 1], [Lf, -1]].forEach(function (pair) {
        var list = pair[0], side = pair[1];
        list.forEach(function (i, k) {
          var s = st.sats[i], y = colY(k, list.length, i, side), x = cx + side * ex(y), guard = 0, box;
          function bx() { var reach = Math.max(18, 13 + s.w); return side > 0 ? [x - 18, y - 18, x + reach, y + 18] : [x - reach, y - 18, x + 18, y + 18]; }
          box = bx();
          while ((hitAny(box, [core], 18) || hitAny(box, obs, 6)) && guard++ < 40) { x += side * 8; box = bx(); }
          x = side > 0 ? Math.min(x, W - 12 - s.w - 12) : Math.max(x, 12 + s.w + 12);
          s.x = x; s.y = y; s.side = side; s.shown = true; box = bx(); satBoxes.push(box);
          s.g.setAttribute('transform', 'translate(' + f1(x) + ' ' + f1(y) + ')'); show(s.g, true); s.g.setAttribute('tabindex', '0');
          attrs(s.name, { x: side > 0 ? 11 : -11, y: -2, 'text-anchor': side > 0 ? 'start' : 'end' });
          attrs(s.kind, { x: side > 0 ? 11 : -11, y: 12, 'text-anchor': side > 0 ? 'start' : 'end' });
          var dx = x - B.cx, dy = y - B.cy, a = B.cw / 2 + 6, b = B.chh / 2 + 6, t = 1 / Math.sqrt((dx / a) * (dx / a) + (dy / b) * (dy / b)), len = Math.hypot(dx, dy) || 1;
          var sx = B.cx + dx * t, sy = B.cy + dy * t, exx = x - dx / len * (s.rr + 4), eyy = y - dy / len * (s.rr + 4);
          s.link.setAttribute('d', t < 1 ? 'M' + f1(sx) + ' ' + f1(sy) + 'L' + f1(exx) + ' ' + f1(eyy) : '');
        });
      });
      var seenG = {};
      [[R, 1], [Lf, -1]].forEach(function (pair) {
        var list = pair[0], side = pair[1];
        list.forEach(function (i, k) {
          var s = st.sats[i], rg = ringOf(s.r.cls), prev = k ? ringOf(st.sats[list[k - 1]].r.cls) : -1;
          if (rg === prev || seenG[rg]) return; seenG[rg] = 1;
          var e = st.grpLab[rg], w = txtW(e, 10), gx = s.x + side * 11, gy = s.y - 20;
          attrs(e, { x: gx, y: gy, 'text-anchor': side > 0 ? 'start' : 'end' }); show(e, true);
          satBoxes.push(side > 0 ? [gx - 2, gy - 10, gx + w + 2, gy + 3] : [gx - w - 2, gy - 10, gx + 2, gy + 3]);
        });
      });
      st.grpLab.forEach(function (e, rg) { if (!seenG[rg]) show(e, false); });
      [1, -1].forEach(function (side, j) {
        var m = side > 0 ? R.length : Lf.length; if (!m) { st.arcs[j].setAttribute('d', ''); return; }
        var col = side > 0 ? R : Lf, ya = Math.max(top, colY(0, m, col[0], side) - 30), yb = Math.min(yLow, colY(m - 1, m, col[m - 1], side) + 30), d = '';
        for (var q = 0; q <= 24; q++) { var yy = ya + (yb - ya) * q / 24, xx = cx + side * ex(yy); d += (q ? 'L' : 'M') + f1(xx) + ' ' + f1(yy); }
        st.arcs[j].setAttribute('d', d);
      });
    }
    function placeGrid() {
      st.arcs.forEach(function (a) { a.setAttribute('d', ''); }); st.orb = null;
      st.grpLab.forEach(function (e) { show(e, false); });
      var gTop = yT + gridPad + 8, cellW = (W - 24) / Math.max(1, cols), m = Math.min(n, cols * rows), per = Math.max(1, Math.ceil(m / Math.max(1, rows)));
      st.ord.forEach(function (i, k) {
        var s = st.sats[i];
        if (k >= m) { s.shown = false; show(s.g, false); s.g.setAttribute('tabindex', '-1'); s.link.setAttribute('d', ''); return; }
        var row = Math.floor(k / per), col = k % per, inRow = row === rows - 1 ? m - row * per : per;
        var xs = 12 + (W - 24 - inRow * cellW) / 2, x = xs + cellW * (col + 0.5), y = gTop + row * rowH;
        s.x = x; s.y = y; s.side = 0; s.shown = true;
        var hitHalf = Math.max(18, s.w / 2 + 4); satBoxes.push([x - hitHalf, y - 18, x + hitHalf, y + 35]);
        s.g.setAttribute('transform', 'translate(' + f1(x) + ' ' + f1(y) + ')'); show(s.g, true); s.g.setAttribute('tabindex', '0');
        attrs(s.name, { x: 0, y: 17, 'text-anchor': 'middle' });
        attrs(s.kind, { x: 0, y: 30, 'text-anchor': 'middle' });
        s.link.setAttribute('d', rows === 1 ? 'M' + f1(x) + ' ' + f1(y - s.rr - 12) + 'L' + f1(x) + ' ' + f1(y - s.rr - 3) : '');
      });
    }

    var placed = [], beadBoxes = st.dots.filter(function (d) { return d.r > 0; }).map(function (d) { return [d.x - d.r - 1, d.y - d.r - 1, d.x + d.r + 1, d.y + d.r + 1, d]; });
    if (band) beadBoxes = beadBoxes.concat(band.boxes);
    var fixed = [[cx - tw / 2 - 6, yT - 11, cx + tw / 2 + 6, yT + 3]].concat(st.ruleBoxes || []);
    [st.chNo0, st.chNo1].forEach(function (t) {
      if (t.getAttribute('visibility') === 'hidden') return;
      var w = txtW(t, 10), x = +t.getAttribute('x'), y = +t.getAttribute('y'), leftward = (t === st.chNo0) !== tight;
      fixed.push([leftward ? x - w - 2 : x - 2, y - 10, leftward ? x + 2 : x + w + 2, y + 3]);
    });
    var cbox = [B.cx - B.cw / 2, B.cy - B.chh / 2, B.cx + B.cw / 2, B.cy + B.chh / 2];
    var arcBoxes = [];
    st.cause.arcs.forEach(function (a) {
      var A = st.dots[a.ka], Bz = st.dots[a.kb];
      if (!A || !Bz || !(A.x >= 0) || !(Bz.x >= 0) || N < 2) { a.el.setAttribute('d', ''); a.hit.setAttribute('d', ''); return; }
      var dx = Bz.x - A.x, h = clamp(Math.abs(dx) * 0.22, 14, 46), ra = Math.max(A.r, 2) + 2, rb = Math.max(Bz.r, 2) + 3;
      var sx = A.x, sy = A.y - ra, ex2 = Bz.x, ey = Bz.y - rb, qx = (sx + ex2) / 2, qy = Math.min(sy, ey) - 2 * h;
      var dd = 'M' + f1(sx) + ' ' + f1(sy) + 'Q' + f1(qx) + ' ' + f1(qy) + ' ' + f1(ex2) + ' ' + f1(ey);
      a.el.setAttribute('d', dd); a.hit.setAttribute('d', dd);
      for (var q = 1; q < 8; q++) { var t = q / 8, px = (1 - t) * (1 - t) * sx + 2 * t * (1 - t) * qx + t * t * ex2, py = (1 - t) * (1 - t) * sy + 2 * t * (1 - t) * qy + t * t * ey; arcBoxes.push([px - 3, py - 3, px + 3, py + 3]); }
    });
    st.causeSelf.forEach(function (c) { var d = st.dots[c.k]; if (d && d.r > 0) { attrs(c.el, { cx: d.x, cy: d.y, r: d.r + 3.2 }); show(c.el, true); } else show(c.el, false); });
    var obsL = satBoxes.concat(E.labsSw || E.labs, E.hud, fixed, [cbox], arcBoxes);
    st.avoid = { fixed: fixed, sats: satBoxes, beads: beadBoxes, labs: E.labsSw || E.labs, hud: E.hud, W: W, top: top, bottom: bottom };
    st.dots.forEach(function (d) { if (d.lab) show(d.lab, false); });
    var Mseg = clamp(Math.round(chord / 120), 2, 9), segs = g.CLSkyCompassBand && CLSkyCompassBand.slots ? CLSkyCompassBand.slots(st.dots, x0, x1, Mseg) : [];
    st.dots.forEach(function (d) { d.labBox = null; });
    segs.forEach(function (sl) {
      sl.list.slice(0, 4).some(function (d) {
        ensureLab(d);
        var w = txtW(d.lab, 11), ok = null, rr = band ? Math.max(d.r, band.hMax + 1) : d.r;
        [[d.y + rr + 14, 'below'], [d.y - rr - 6, 'above']].some(function (p) {
          var box = [d.x - w / 2 - 3, p[0] - 11, d.x + w / 2 + 3, p[0] + 3];
          if (box[0] < 6 || box[2] > W - 6 || box[3] > bottom) return false;
          if (hitAny(box, obsL, 2) || hitAny(box, placed, 12) || beadBoxes.some(function (bb) { return bb[4] !== d && box[0] < bb[2] && box[2] > bb[0] && box[1] < bb[3] && box[3] > bb[1]; })) return false;
          ok = [p[0], box]; return true;
        });
        if (!ok) return false;
        attrs(d.lab, { x: d.x, y: ok[0] }); show(d.lab, true); placed.push(ok[1]); d.labBox = ok[1]; return true;
      });
    });
    if (g.CLSkyOrrery && CLSkyOrrery.setTextMask) CLSkyOrrery.setTextMask(satBoxes.concat(E.labsSw || E.labs, placed, fixed), VW, VH);
    st.labBoxes = placed;
    st.budget = { y0: Math.round(y0), sag: Math.round(sag), chord: Math.round(chord), rows: rows, cols: cols, bottom: Math.round(bottom), noteHt: noteHt };
    if (renderNote(E, W) || !st.noteSeen) { st.noteSeen = true; st.noteCheck = true; }
    if (g.CLSkyCompassDrag) CLSkyCompassDrag.relayout();
    if (g.CLSkyCompassFan) CLSkyCompassFan.relayout();
  }

  function sw(cls) { return '<svg class="skc-sw" viewBox="0 0 24 6" aria-hidden="true"><line class="' + cls + '" x1="1" y1="3" x2="23" y2="3"/></svg>'; }
  function renderNote(E, W) {
    if (!note) return;
    var counts = {}, order = [], shownN = 0;
    st.sats.forEach(function (s) { if (!s.shown) return; shownN++; var c = s.r.cls; if (!counts[c]) { counts[c] = 0; order.push(c); } counts[c]++; });
    order.sort(function (a, b) { return relRank(a) - relRank(b); });
    var parts = [];
    order.forEach(function (c) { parts.push('<span class="lg skc-lg">' + sw('skc-link r-' + c) + esc(relLabel(c)) + ' <b>' + counts[c] + '</b></span>'); });
    var rest = st.total - shownN;
    if (!st.total) parts.push('<span class="lg skc-lg-sum">暂无联系记录</span>');
    else if (rest > 0 || W > 560) parts.push('<span class="lg skc-lg-sum">' + (rest > 0 ? '另 ' + rest + ' 位未列 · ' : '') + '共 ' + st.total + ' 位联系</span>');
    if (st.nCause) parts.push('<span class="lg skc-lg">' + sw('skc-cause') + '因果记录 <b>' + st.nCause + '</b></span>');
    if (E.gl) parts.push('<span class="lg skc-lg">' + sw('skc-sw-ref') + '点线 = 未建档参考轮廓（非数据）</span>');
    var html = parts.join(''), ins = Math.round((opts.inset && opts.inset.right) || 0) + 'px', changed = false;
    if (note.style.getPropertyValue('--skc-inset-r') !== ins) { note.style.setProperty('--skc-inset-r', ins); changed = true; }
    if (html !== st.noteKey) { note.innerHTML = html; st.noteKey = html; changed = true; }
    return changed;
  }

  function lightEvent(k) {
    var d = st.dots[k]; if (!d) return;
    var cast = d.o.e.characters || [];
    st.sats.forEach(function (s) { var on = cast.indexOf(s.r.name) >= 0; s.g.classList.toggle('is-lit', on); s.link.classList.toggle('is-lit', on); });
    st.dots.forEach(function (x, j) { if (x.el) x.el.classList.toggle('is-on', j === k); if (x.lab) x.lab.classList.toggle('is-on', j === k); });
    st.cause.arcs.forEach(function (x) { x.el.classList.toggle('is-on', x.ka === k || x.kb === k); });
    if (st.bandCur) { var cur = st.band && !d.el; if (cur) attrs(st.bandCur, { cx: d.x, cy: d.y, r: 3.2 }); show(st.bandCur, cur); }
    svg.classList.add('skc-emph');
    showCard('<div class="sc-k">' + esc(d.o.chapter) + ' · ' + (d.o.count > 1 ? d.o.count + ' 个事件' + (d.o.keyCount ? ' · ' + d.o.keyCount + ' 关键' : '') : esc(d.o.e.kind || '')) + '</div><div class="sc-t">' + esc(d.o.e.title || '') + '</div>' + (d.o.count > 1 && g.CLSkyCompassFan ? '' : '<div class="sc-c">' + esc(d.o.e.summary || '') + '</div>') + '<div class="sc-m">同场：' + esc(cast.filter(function (n) { return n !== st.name; }).slice(0, 8).join('、') || '—') + '</div>', d.x, d.y);
    if (g.CLSkyCompassFan) CLSkyCompassFan.open(k);
  }
  function lightSat(i) {
    var s = st.sats[i]; if (!s) return;
    var shared = st.dots.filter(function (d) { return (d.o.e.characters || []).indexOf(s.r.name) >= 0; });
    st.dots.forEach(function (d) { var on = shared.indexOf(d) >= 0; if (d.el) d.el.classList.toggle('is-on', on); if (d.lab) d.lab.classList.toggle('is-on', on); });
    if (st.band && st.bandSel) st.bandSel.setAttribute('d', g.CLSkyCompassBand.subset(st.band, function (d) { return shared.indexOf(d) >= 0; }));
    st.sats.forEach(function (x, j) { x.g.classList.toggle('is-lit', j === i); x.link.classList.toggle('is-lit', j === i); });
    svg.classList.add('skc-emph'); if (g.CLSkyCompassFan) CLSkyCompassFan.close();
    showCard('<div class="sc-k">' + esc(s.r.derived ? '同场 · 由事件推导' : s.r.clsLabel + ' · ' + s.r.kind) + '</div><div class="sc-t">' + esc(s.r.name) + '</div><div class="sc-m">共同出场 ' + shared.length + ' 个章节段' + (shared.length ? ' · ' + esc(shared[0].o.chapter) + (shared.length > 1 ? ' — ' + esc(shared[shared.length - 1].o.chapter) : '') : '') + '</div>' + (s.r.desc && !s.r.derived ? '<div class="sc-c">' + esc(s.r.desc) + '</div>' : '') + '<div class="sc-m">点击进入 ' + esc(s.r.name) + ' 的罗盘</div>', s.x, s.y);
  }
  function unlight() {
    if (!st) return; svg.classList.remove('skc-emph');
    st.sats.forEach(function (x) { x.g.classList.remove('is-lit'); x.link.classList.remove('is-lit'); });
    st.dots.forEach(function (x) { if (x.el) x.el.classList.remove('is-on'); if (x.lab) x.lab.classList.remove('is-on'); });
    if (st.bandSel) st.bandSel.setAttribute('d', ''); if (st.bandCur) show(st.bandCur, false); st.bandK = -1;
    st.cause.arcs.forEach(function (x) { x.el.classList.remove('is-on'); });
    svg.card.hidden = true; if (g.CLSkyCompassFan) CLSkyCompassFan.close();
  }
  function showCard(html, x, y) {
    var c = svg.card; c.innerHTML = html; c.hidden = false;
    var w = c.offsetWidth || 240, h = c.offsetHeight || 90, left = x + 16, top = y - h - 12;
    if (left + w > g.innerWidth - 12) left = x - w - 16;
    if (top < 76) top = y + 16;
    if (top + h > g.innerHeight - 8) top = Math.max(76, g.innerHeight - 8 - h);
    c.style.setProperty('--sc-x', Math.max(12, left).toFixed(0) + 'px'); c.style.setProperty('--sc-y', top.toFixed(0) + 'px');
  }
  function target(e) { var t = e.target; return t && t.closest ? t.closest('[data-sat],[data-ev],[data-cause]') : null; }
  function lightCause(j) {
    var a = st.cause.arcs[j]; if (!a) return;
    var A = st.dots[a.ka], B = st.dots[a.kb];
    st.cause.arcs.forEach(function (x, i) { x.el.classList.toggle('is-on', i === j); });
    st.dots.forEach(function (x, i) { if (x.el) x.el.classList.toggle('is-on', i === a.ka || i === a.kb); });
    svg.classList.add('skc-emph');
    var G = opts.graph, ea = G.events[a.c.a] || {}, eb = G.events[a.c.b] || {};
    showCard('<div class="sc-k">因果 · ' + esc(a.c.basis || '未核验') + ' · ' + esc(A.o.chapter) + ' → ' + esc(B.o.chapter) + '</div><div class="sc-t">' + esc(ea.title || '') + ' → ' + esc(eb.title || '') + '</div>' +
      (a.c.desc ? '<div class="sc-c">' + esc(a.c.desc) + '</div>' : '') + (a.c.quote ? '<div class="sc-m">原文：「' + esc(short(a.c.quote, 40)) + '」</div>' : ''), (A.x + B.x) / 2, Math.min(A.y, B.y) - 20);
  }
  function onBandMove(e) {
    if (!st || !st.band || !e.target || !e.target.hasAttribute || !e.target.hasAttribute('data-band')) return;
    var k = st.band.nearest(e.clientX);
    if (k !== st.bandK) { st.bandK = k; lightEvent(k); }
  }
  function onBandOut(e) { if (st && e.target && e.target.hasAttribute && e.target.hasAttribute('data-band')) unlight(); }
  function onOver(e) { var t = target(e); if (!t || !st) return; if (t.hasAttribute('data-sat')) lightSat(+t.getAttribute('data-sat')); else if (t.hasAttribute('data-cause')) lightCause(+t.getAttribute('data-cause')); else lightEvent(+t.getAttribute('data-ev')); }
  function onOut(e) { var t = target(e); if (!t) return; var to = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('[data-sat],[data-ev],[data-cause]') : null; if (to === t) return; unlight(); }
  function onClick(e) { var t = target(e); if (!t || !st) return; if (t.hasAttribute('data-sat')) { var s = st.sats[+t.getAttribute('data-sat')]; if (s && opts.onPick) { unlight(); opts.onPick(s.r.name); } } }
  doc.addEventListener('keydown', function (e) { if (!st || (e.key !== 'Enter' && e.key !== ' ')) return; var t = e.target && e.target.closest && e.target.closest('[data-sat]'); if (!t) return; e.preventDefault(); var s = st.sats[+t.getAttribute('data-sat')]; if (s && opts.onPick) opts.onPick(s.r.name); });

  var FONT_CLS = ['skc-sat-name', 'skc-sat-kind', 'skc-ev-label', 'skc-ch', 'skc-chain-title'];
  var warm = null;
  function idle(fn) { if (g.requestIdleCallback) g.requestIdleCallback(fn, { timeout: 5000 }); else setTimeout(function () { fn(null); }, 80); }
  function glyphSet(V) {
    var seen = {}, out = [];
    function add(t) { t = String(t || ''); for (var i = 0; i < t.length; i++) { var ch = t.charAt(i); if (!seen[ch]) { seen[ch] = 1; out.push(ch); } } }
    (V.characters || []).forEach(function (c) { add(c.name); });
    (V.relations || []).forEach(function (r) { add(r.kind); });
    (V.events || []).forEach(function (e) { add(String(e.title || '').slice(0, 6)); });
    add('第回事件链·0123456789…◆ 暂无记录同场');
    return out.join('');
  }
  function warmStep(dl) {
    if (!warm) return;
    try {
      do {
        if (warm.step === 0) {
          ensureSvg(); if (!mctx) mctx = doc.createElement('canvas').getContext('2d');
          warm.fonts = FONT_CLS.map(function (c) { var t = mk('text', c, svg), f = fontFor(t); svg.removeChild(t); return f.font; });
          warm.step = 1;
        } else if (warm.step === 1) {
          mctx.font = warm.fonts[warm.fi]; mctx.measureText(warm.glyphs.slice(warm.ci, warm.ci + 120)); warm.ci += 120;
          if (warm.ci >= warm.glyphs.length) { warm.ci = 0; if (++warm.fi >= warm.fonts.length) warm.step = 2; }
        } else {
          var GM = g.CLGemModel, S = warm.A.scene ? warm.A.scene() : null;
          if (S && S.metaOf && GM && GM.build && warm.V.characters.length) GM.build(warm.V.characters[0], warm.V, { metaOf: S.metaOf });
          warm = null; return;
        }
      } while (dl && !dl.didTimeout && dl.timeRemaining() > 4);
    } catch (e) { warm = null; return; }
    idle(warmStep);
  }
  function prewarm() {
    var A = g.CLApp, V = A && A.atlas && A.atlas.skyView ? A.atlas.skyView() : null;
    if (!V || !V.characters || !V.characters.length) return;
    warm = { A: A, V: V, glyphs: glyphSet(V), fonts: null, fi: 0, ci: 0, step: 0 };
    idle(warmStep);
  }
  doc.addEventListener('cl:graph-ready', function () { warm = null; setTimeout(prewarm, 4500); });

  g.CLSkyCompass = {
    open: open, close: close, frame: frame, prewarm: prewarm,
    setInset: function (ins) { if (opts) { opts.inset = ins; lastKey = ''; frame(); } },
    eventInfo: function (k) { var x = st && st.dots[k]; return x ? { no: x.o.no, chapter: x.o.chapter, kind: x.o.count > 1 ? x.o.count + ' 个事件' : (x.o.e.kind || ''), title: x.o.e.title || '', count: x.o.count || 1, cast: (x.o.e.characters || []).slice() } : null; },
    hoverEvent: function (k) { if (!st || !st.dots[k]) return false; if (st.dirty || !st.env) frame(); lightEvent(k); return true; }, hoverSat: function (i) { if (!st || !st.sats[i]) return false; lightSat(i); return true; }, unhover: function () { unlight(); },
    keyEvents: function () { if (st && (st.dirty || !st.env)) frame(); return st ? st.dots.map(function (d, k) { return d.o.key && (!st.band || st.band.shown[k]) ? k : -1; }).filter(function (k) { return k >= 0; }) : []; },
    satellites: function () { return st ? st.sats.map(function (s) { return { name: s.r.name, cls: s.r.cls, kind: s.r.kind, derived: s.r.derived, strength: s.r.strength || 0 }; }) : []; },
    stats: function () { return st ? { open: true, name: st.name, satellites: st.sats.length, more: st.more, total: st.total, events: st.dots.length, eventCount: st.nEv, band: !!st.band, beadsShown: st.dots.filter(function (d) { return d.r > 0; }).length, chainNodes: st.gDots ? st.gDots.childNodes.length + st.gSteps.childNodes.length + svg.gChainLab.childNodes.length : 0, derived: !!(st.rels[0] && st.rels[0].derived), mode: st.mode || null, causes: st.nCause || 0, causeArcs: st.cause.arcs.length, labels: (st.labBoxes || []).length,
      labelTitles: st.dots.filter(function (d) { return d.labBox && d.lab; }).map(function (d) { return d.lab.textContent; }),
      groups: st.sats.map(function (s) { return ringOf(s.r.cls); }) } : { open: false }; },
    _layout: function (satsOnly) {
      if (!st) return null;
      var sats = st.sats.map(function (s, i) { return { i: i, name: s.r.name, x: s.x, y: s.y, cls: s.r.cls, side: s.side || 0, rr: s.rr, on: s.g.getAttribute('visibility') !== 'hidden' }; }).filter(function (s) { return s.on; });
      if (satsOnly) return { mode: st.mode || null, sats: sats, orb: st.orb || null, B: st.B || null };
      return { mode: st.mode || null, sats: sats, orb: st.orb || null,
        dots: st.dots.map(function (d) { return { x: d.x, y: d.y, r: d.r, key: d.o.key, count: d.o.count }; }),
        labels: (st.labBoxes || []).map(function (b) { return b.map(Math.round); }), budget: st.budget || null };
    }
  };
})(window);
