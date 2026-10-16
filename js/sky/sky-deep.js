(function (g) {
  'use strict';
  var doc = document;
  var T = null, S = null, disc = null, field = null, app = null;
  var cosmos = null, post = null, stars = null, trails = null, neb = null, bun = null, rings = null, fx = null, orb = null, sats = null, view = null, scale = null, rev = null;
  var heroKey = null, cosmosReady = false, homeSet = false, homeDir = null;
  var M = null, G = null, mode = 'constellation', inited = false, discRev = -1, skyRef = null, liveUntil = 0, clock = 0, tierName = '';
  var reading = false;
  var structureOn = false, structureProgress = 0, structureTw = null, structureButton = null, structureLegend = null;
  function clip(v) { return Math.max(0, Math.min(1, v)); }
  function paintStructure(p) {
    structureProgress = clip(p);
    var time = structureProgress * T.DUR.structure;
    var env = clip(time / T.DUR.structureEnv), face = clip((time - T.DUR.structureEnv) / (T.DUR.structureFace - T.DUR.structureEnv));
    [cosmos, neb].forEach(function (layer) { if (layer && layer.setStructure) layer.setStructure(env); });
    [stars, rings, fx, orb].forEach(function (layer) { if (layer && layer.setStructure) layer.setStructure(face); });
    if (S && S.setStructureMix) S.setStructureMix(face * (1 - T.ALPHA.structureKeep));
    doc.body.classList.toggle('sk-structure', structureProgress > 0);
    if (structureLegend) {
      structureLegend.hidden = !structureProgress;
      structureLegend.style.opacity = String(clip((time - T.DUR.structureFace) / (T.DUR.structureLegend - T.DUR.structureFace)));
    }
  }
  function announceStructureState() {
    var detail = { on: structureOn, progress: structureProgress,
      ready: structureOn && structureProgress >= 1 && !structureTw };
    var event;
    if (typeof g.CustomEvent === 'function') event = new g.CustomEvent('cl:sky-structure-state', { detail: detail });
    else { event = doc.createEvent('CustomEvent'); event.initCustomEvent('cl:sky-structure-state', false, false, detail); }
    doc.dispatchEvent(event);
  }
  function setStructure(on, instant) {
    if (!inited) return false;
    on = !!on;
    if (on === structureOn && !instant) return on;
    structureOn = on;
    placeStructureLegend();
    if (structureTw) { structureTw.cancel(); structureTw = null; }
    if (on) {
      if (g.CLSky && g.CLSky.stop) g.CLSky.stop();
      if (g.CLSky && g.CLSky.finishParticipants) g.CLSky.finishParticipants();
      if (view && view.tour) view.tour(false);
      if (S && S.cancelCameraMotion) S.cancelCameraMotion();
    }
    if (structureButton) {
      var longLabel = structureButton.querySelector('.sk-structure-long'), shortLabel = structureButton.querySelector('.sk-structure-short');
      if (longLabel) longLabel.textContent = on ? '返回实体' : '看清结构';
      if (shortLabel) shortLabel.textContent = on ? '实体' : '结构';
      structureButton.setAttribute('aria-label', on ? '返回实体' : '看清结构');
      structureButton.setAttribute('aria-pressed', String(on));
    }
    if (instant || reduced()) { paintStructure(on ? 1 : 0); announceStructureState(); }
    else structureTw = CLSkyMotion.tween({from: structureProgress, to: on ? 1 : 0,
      dur: on ? T.DUR.structure : T.DUR.structureBack, ease: function (v) { return v; },
      tag: 'structure', onUpdate: paintStructure, onDone: function () { structureTw = null; announceStructureState(); }});
    if (!on && !instant && !reduced()) announceStructureState();
    return on;
  }
  function finishStructure() { if (structureTw) { CLSkyMotion.finishAll('structure'); structureTw = null; announceStructureState(); } }
  function placeStructureLegend() {
    if (!structureLegend) return;
    var top = doc.querySelector('.sky-top'), crumb = doc.querySelector('.sky-crumb:not([hidden])');
    var y = top ? top.getBoundingClientRect().bottom : 60;
    if (crumb) y = Math.max(y, crumb.getBoundingClientRect().bottom);
    structureLegend.style.top = Math.round(y + 8) + 'px'; structureLegend.style.bottom = 'auto';
  }
  function mountStructure() {
    if (structureButton) return;
    var host = doc.querySelector('.sky-actions'); if (!host) return;
    structureButton = doc.createElement('button'); structureButton.id = 'skyStructure'; structureButton.type = 'button';
    structureButton.className = 'sky-plot sky-structure-button'; structureButton.innerHTML = '<span class="sk-structure-long">看清结构</span><span class="sk-structure-short">结构</span>'; structureButton.setAttribute('aria-label', '看清结构'); structureButton.setAttribute('aria-pressed', 'false');
    structureButton.setAttribute('aria-controls', 'skyStructureLegend'); structureButton.addEventListener('click', function () { setStructure(!structureOn); });
    host.appendChild(structureButton);
    structureLegend = doc.createElement('aside'); structureLegend.id = 'skyStructureLegend'; structureLegend.className = 'sky-structure-legend'; structureLegend.hidden = true;
    structureLegend.textContent = '结构阅读 · 实线看连接，箭头看因果；颜色与原图一致。';
    doc.body.appendChild(structureLegend);
    g.addEventListener('resize', placeStructureLegend);
    placeStructureLegend();
  }
  var blur = 0, blurTw = null, revealTw = null, igniteTw = null, homeTw = null, lastHome = 0, exitHold = null, compassT = -1e9;
  var hoverStar = null, hotCamp = null, pointer = { x: 0, y: 0 }, evCount = {}, relCount = {}, lineIdx = null;
  var KEY = /转折|高燃|抉择|冲突|高潮|揭秘/;
  var cards = g.CLSkyDeepCards.create({
    scene: function () { return S; }, graph: function () { return G; }, model: function () { return M; },
    app: function () { return app; }, tokens: function () { return T; }, info: sky, color: groupColor,
    events: function () { return evCount; }, relations: function () { return relCount; },
    enabled: function () { return inited; }, mode: function () { return mode; }, pointer: pointer,
    stars: function () { return stars; }, bundles: function () { return bun; }, nebula: function () { return neb; },
    hoverStar: function () { return hoverStar; }, setHoverStar: function (v) { hoverStar = v; },
    hotCamp: function () { return hotCamp; }, setHotCamp: function (v) { hotCamp = v; }, hop: hop, sectorIndex: sectorIndex
  });
  var hideCard = cards.hide, lineCard = cards.line, onStarHover = cards.hoverStar, onCampHover = cards.hoverCamp;
  var toolbar = g.CLSkyDeepViews.create({ view: function () { return view; }, mode: function () { return mode; } });
  var buildViews = toolbar.mount, syncViews = toolbar.sync;

  function now() { return clock; }
  function reduced() { return !!(T && T.reduced()); }
  function sky() { return S && S.skyInfo ? S.skyInfo() : null; }
  var mk = g.CLSkyUtil.mk;
  function sectorIndex(info, camp) {
    if (!info) return -1;
    var name = camp || '散星';
    for (var i = 0; i < info.sectors.length; i++) if (info.sectors[i].name === name) return i;
    for (var k = 0; k < info.sectors.length; k++) if (info.sectors[k].field) return k;
    return -1;
  }
  function groupColor(info, camp) { var i = sectorIndex(info, camp); return i >= 0 ? info.sectors[i].color : T.FAMILY[''][0]; }

  var dna = null;

  function buildStars() {
    var info = sky(), list = [], wmax = 1;
    G.characters.forEach(function (c) { var n = S.nodeOf('c:' + c.name); if (n) wmax = Math.max(wmax, n.w || 0); });
    var order = G.characters.map(function (c) { var n = S.nodeOf('c:' + c.name); return { c: c, n: n, w: n ? n.w || 0 : 0 }; }).filter(function (o) { return o.n; })
      .sort(function (a, b) { return b.w - a.w; });
    order.forEach(function (o, rank) {
      var col = groupColor(info, o.n.camp), villain = o.c.role === '反派';
      list.push({ key: 'c:' + o.c.name, name: o.c.name, tier: o.n.tier, w01: o.w / wmax,
        core: T.mix(T.C.STAR_WHITE, villain ? T.C.OPPOSE : col, villain ? 0.35 : 0.22), halo: col,
        reveal: rev ? rev.starReveal(o.n, info, order.length > 1 ? rank / (order.length - 1) : 0) : order.length > 1 ? 0.85 * rank / (order.length - 1) : 0 });
    });
    heroKey = order.length ? 'c:' + order[0].c.name : null;
    stars.setStars(list);
    if (trails) trails.setStars(list.map(function (o) { return { key: o.key, hex: o.halo }; }), info ? info.R : 1);
  }
  function buildField() {
    var info = sky(); skyRef = info;
    if (!info) { neb.setState('hidden'); bun.setState('hidden'); return; }
    var wmax = 1;
    G.characters.forEach(function (c) { var n = S.nodeOf('c:' + c.name); if (n) wmax = Math.max(wmax, n.w || 0); });
    neb.build({ R: info.R, pitch: info.pitch, rad: Math.min(0.3, Math.max(0.09, 1.02 * (info.s0 || 60) / info.R)), groups: info.sectors.map(function (s) { return { name: s.name, color: s.color }; }),
      stars: G.characters.map(function (c) { var n = S.nodeOf('c:' + c.name); return n ? { key: c.name, group: sectorIndex(info, n.camp), w01: (n.w || 0) / wmax } : null; }).filter(Boolean) });
    bun.build({ R: info.R, pitch: info.pitch, rc: info.rc || 0, ra: info.ra || 0, rb: info.rb || 0,
      sectors: info.sectors.map(function (s) { return { name: s.name, a0: s.a0, a1: s.a1, core: !!s.core, color: s.color }; }),
      threads: field && field.threads ? field.threads() : [], beams: field && field.beams ? field.beams() : [] });
    liveUntil = now() + 3.2;
  }
  function genHex(gen, kind) {
    var c = T.GEN[(gen | 0) % T.GEN.length];
    return kind === 'quiet' ? T.mix(T.C.INK3, c, 0.35) : kind === 'named' ? T.mix(c, T.C.INK2, 0.12) : c;
  }
  function buildRings() {
    var d = disc && disc.desc ? disc.desc() : null; discRev = disc && disc.rev ? disc.rev() : -1;
    if (!d) return;
    lineIdx = {};
    d.items.forEach(function (it) {
      lineIdx[it.id] = it.lineIdx;
      it.color = genHex(it.gen, it.kind);
      it.beads = it.kind === 'quiet' ? [] : it.beads.map(function (b) { var e = G.events[b.ev]; return { a: b.a, key: !!(e && KEY.test(e.kind || '')) }; });
    });
    rings.build(d);
    fx.build({ rIn: d.rIn, rMain: d.rMain, rBez: d.rBez, zMain: d.zMain || 0, zBez: d.zBez || 0,
      bridges: d.bridges.map(function (b) { return { a: b.a, r0: b.r0, r1: b.r1, z0: b.z0 || 0, z1: b.z1 || 0, color: genHex(b.gen, 'named') }; }),
      caps: d.caps.map(function (c) { return { a: c.a, r: c.r, z: c.z || 0, kind: c.kind, color: genHex(c.gen, 'main') }; }) });
  }
  function seedOf(t) { var h = 2166136261, str = String(t || 'castline'); for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) % 100000 + 1; }
  function buildCosmos() {
    if (!cosmos || !S.camera || !S.controls) return;
    var info = sky(), c = S.controls.target, fwd = c.clone().sub(S.camera.position).normalize();
    try {
      cosmos.build({ R: info ? info.R : 400, center: [c.x, c.y, c.z], avoid: [fwd.x, fwd.y, fwd.z], seed: seedOf(G && G.title), dna: dna && T.dna ? T.dna().fields : null });
      cosmos.setState('hidden');
      if (S.core && S.core().setLegacySky) S.core().setLegacySky(false);
    } catch (e) {
      if (g.console) console.warn('[sky-deep] 深空天球构建失败，退回旧背景', e);
      try { cosmos.dispose(); } catch (e2) {}
      cosmos = null;
      if (S.core && S.core().setLegacySky) S.core().setLegacySky(true);
    }
  }
  var _fv = null, _orbV = null;
  function cosmosFocus() {
    if (!S.camera || !S.controls) return;
    var W = g.innerWidth || 1, H = g.innerHeight || 1;
    if (mode === 'compass' && orb && orb.setCenter && S.crownAnchor) {
      var anchor = S.crownAnchor();
      if (anchor) { if (!_orbV) _orbV = new g.THREE.Vector3(); anchor.getWorldPosition(_orbV); orb.setCenter(_orbV); }
    }
    if (mode === 'compass' && S.crownScreenBounds) {
      var b = S.crownScreenBounds();
      if (b && b.right > b.left) {
        if (orb && orb.setOcclusion) orb.setOcclusion(b, W, H);
        if (cosmos) cosmos.setFocus({ cx: (b.left + b.right) / 2, cy: (b.top + b.bottom) / 2, rx: (b.right - b.left) * 0.72, ry: (b.bottom - b.top) * 0.62 });
        return;
      }
    }
    if (!cosmos) return;
    if (!_fv) _fv = new g.THREE.Vector3();
    var info = sky(), R = info ? info.R : 400, d = disc && disc.desc ? disc.desc() : null;
    var k = mode === 'plot' && d ? (d.rBez || 1.8) * 1.08 : 1.12;
    _fv.copy(S.controls.target).project(S.camera);
    var dist = S.camera.position.distanceTo(S.controls.target) || 1, px = R * k * (H / (2 * Math.tan((S.camera.fov || 42) * Math.PI / 360))) / dist;
    cosmos.setFocus({ cx: (_fv.x * 0.5 + 0.5) * W, cy: (-_fv.y * 0.5 + 0.5) * H, rx: px, ry: px });
  }

  var adj = {};
  function counts() {
    evCount = {}; relCount = {}; adj = {};
    G.events.forEach(function (e) { (e.characters || []).forEach(function (n) { evCount[n] = (evCount[n] || 0) + 1; }); });
    var V = app && app.atlas && app.atlas.skyView ? app.atlas.skyView() : G;
    (V.relations || []).forEach(function (r) {
      relCount[r.a] = (relCount[r.a] || 0) + 1; relCount[r.b] = (relCount[r.b] || 0) + 1;
      (adj[r.a] = adj[r.a] || {})[r.b] = 1; (adj[r.b] = adj[r.b] || {})[r.a] = 1;
    });
  }
  function hop(name) { return [name].concat(Object.keys(adj[name] || {})); }

  function starState(s) { stars.setState(s); if (trails) trails.setState(s); }
  function tweenBlur(to, dur) {
    if (blurTw) blurTw.cancel();
    blurTw = CLSkyMotion.tween({ from: blur, to: to, dur: dur, ease: T.EASE.lens, onUpdate: function (v) { blur = v; post.setBlur(v); }, tag: 'deep' });
  }
  function holdExit(fn) {
    if (exitHold) { exitHold.cancel(); exitHold = null; }
    exitHold = CLSkyMotion.tween({ from: 0, to: 1, dur: 0.01, delay: T.DUR.flick, tag: 'deep',
      onDone: function () { exitHold = null; fn(); } });
  }
  function setMode(m, name) {
    if (!inited) return;
    if (structureOn || structureTw || structureProgress > 0) setStructure(false, true);
    var prev = mode; mode = m;
    if (prev === 'compass') compassT = clock;
    var fromCompass = clock - compassT < 0.15;
    if (m !== 'compass' && exitHold) { exitHold.cancel(); exitHold = null; }
    if (view) { if (view.useHome) view.useHome(m === 'plot' ? 'plot' : 'constellation'); if (m === 'compass' && view.current().tour) view.tour(false); }
    doc.body.classList.toggle('skd-plot', m === 'plot');
    if (prev === 'compass' && m !== 'compass' && homeStale) refreshHome();
    if (S.setBoost) S.setBoost(null, m);
    if (cosmos && cosmos.setDefocus) cosmos.setDefocus(m === 'compass' ? 1 : m === 'plot' ? 0.35 : 0);
    if (m === 'plot') {
      tweenBlur(0, T.DUR.focus);
      rings.setState('plot'); fx.setState('plot');
      starState('dim'); neb.setState('dim'); bun.setState('dim'); bun.emphasize({ group: -1, star: null }); stars.setLit(null); neb.hover(-1);
      if (fromCompass) CLSkyMotion.tween({ from: 0, to: 1, dur: 0.01, delay: T.DUR.flick * 0.5, tag: 'deep', onDone: function () { if (mode === 'plot') neb.setState('dim', true); } });
      if (prev !== 'plot') {
        rings.reveal(0);
        if (revealTw) revealTw.cancel();
        revealTw = CLSkyMotion.tween({ from: 0, to: 1, dur: fromCompass ? 1.2 : T.DUR.unfurl, delay: fromCompass ? 0.05 : 0.25, ease: T.EASE.inOut, onUpdate: function (v) { rings.reveal(v); }, tag: 'deep' });
      }
      orb.close(); hideCard();
      if (cosmos) cosmos.setState('show');
    } else if (m === 'compass') {
      if (cosmos) cosmos.setState('dim');
      tweenBlur(0, 0);
      if (prev !== 'compass') holdExit(function () { rings.setState('hidden'); fx.setState('hidden'); starState('hidden'); neb.setState('hidden'); bun.setState('hidden'); });
      else { rings.setState('hidden'); fx.setState('hidden'); starState('hidden'); neb.setState('hidden'); bun.setState('hidden'); }
      stars.setLit(null); hideCard();
      var anchor = S.crownAnchor ? S.crownAnchor() : null, info = sky(), n = name ? S.nodeOf('c:' + name) : null;
      if (anchor && g.THREE) {
        var v = new g.THREE.Vector3(); anchor.getWorldPosition(v);
        orb.open({ center: v, radius: 150, color: n ? groupColor(info, n.camp) : T.C.BRASS });
        bindSats();
      }
      cascade();
      if (prev !== 'compass') flare();
    } else {
      tweenBlur(T.BLUR.backdrop, prev === 'compass' ? 0.01 : T.DUR.focus);
      rings.setState('backdrop'); fx.setState('hidden'); starState('show'); neb.setState('show'); bun.setState('show');
      if (fromCompass) CLSkyMotion.tween({ from: 0, to: 1, dur: 0.01, delay: T.DUR.flick * 0.5, tag: 'deep', onDone: function () { if (mode === 'constellation') neb.setState('show', true); } });
      rings.setEmph(-1, -1); rings.setCursor(-1); fx.setNeedle(null); fx.setWake(null); fx.setWedge(null); stars.setLit(null);
      if (revealTw) { revealTw.cancel(); revealTw = null; } rings.reveal(1);
      orb.close(); if (cards.kind() === 'axis') hideCard();
      if (cosmos) cosmos.setState('show');
    }
    applyReadingLight();
    syncViews();
  }

  function applyReadingLight() {
    if (!inited) return false;
    if (mode !== 'constellation') return false;
    if (cosmos) cosmos.setState(reading ? 'dim' : 'show');
    neb.setState(reading ? 'dim' : 'show');
    if (cosmos && cosmos.setCalm) cosmos.setCalm(reading ? 1 : 0);
    return reading;
  }
  function readingFocus(name, partners) {
    var lit = bun && bun.emphasize ? (bun.emphasize({ group: -1, star: name || null }) | 0) : 0;
    if (stars && stars.setLit) stars.setLit(name ? [name].concat(partners || []) : null);
    return lit;
  }
  function clearReadingFocus() {
    if (bun && bun.emphasize) bun.emphasize({ group: -1, star: null });
    if (stars && stars.setLit) stars.setLit(null);
  }
  function setReading(on) {
    on = !!on;
    if (on === reading) return reading;
    reading = on;
    if (g.document && g.document.body) {
      g.document.body.classList.toggle('sk-reading', reading);
      if (!reading) g.document.body.classList.remove('sk-rail-peek');
    }
    applyReadingLight();
    return reading;
  }

  var ORB_RING = { ally: 0, kin: 0, bond: 0, oppose: 1, dark: 1 }, ORB_NAME = ['内 亲近', '中 对抗', '外 其他'];
  function bindSats() {
    if (!sats || !g.CLSkyCompass) return;
    var list = CLSkyCompass.satellites(), kmax = 0, used = [0, 0, 0];
    list.forEach(function (s) { kmax = Math.max(kmax, s.strength || 0); });
    sats.set(orb.rig(), list.map(function (s) {
      var r = ORB_RING[s.cls] != null ? ORB_RING[s.cls] : 2; used[r]++;
      return { ring: r, hex: T.relHex(s.cls), k: kmax > 0 ? (s.strength || 0) / kmax : 0.5 };
    }));
    var note = doc.querySelector('.skc-note'), txt = ORB_NAME.filter(function (x, i) { return used[i] > 0; }).join(' · ');
    if (note) { if (txt && tierName !== 'low') note.setAttribute('data-orbit', txt); else note.removeAttribute('data-orbit'); }
    syncHot();
  }
  function syncHot() {
    var idx = [];
    Array.prototype.forEach.call(doc.querySelectorAll('.sky-compass .skc-sat.is-lit'), function (el) { idx.push(+el.getAttribute('data-sat')); });
    sats.setHot(idx);
  }
  function onSatSync(e) {
    if (!inited || mode !== 'compass' || !sats || !e.target.closest || !e.target.closest('.sky-compass')) return;
    syncHot();
  }
  var cascadeTimer = 0;
  function cascade() {
    var el = doc.querySelector('.sky-compass'); if (!el) return;
    if (cascadeTimer) { clearTimeout(cascadeTimer); cascadeTimer = 0; }
    el.classList.remove('skd-cascade');
    if (reduced()) return;
    function stagger(list) { var n = list.length; Array.prototype.forEach.call(list, function (x, k) { x.style.setProperty('--skd-i', n > 1 ? (k / (n - 1)).toFixed(3) : '0'); }); }
    stagger(el.querySelectorAll('.skc-ev')); stagger(el.querySelectorAll('.skc-sat')); stagger(el.querySelectorAll('.skc-link'));
    el.classList.add('skd-cascade');
    cascadeTimer = setTimeout(function () { el.classList.remove('skd-cascade'); cascadeTimer = 0; }, (T.DUR.fly + T.DUR.focus) * 1000 + 100);
  }

  var flareTw = null;
  function flare() {
    var core = S.core && S.core(), bloom = core && core.getBloom ? core.getBloom() : null;
    if (!bloom || reduced()) return;
    if (flareTw) flareTw.cancel();
    var base = bloom.strength;
    flareTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.dive, ease: function (t) { return t; },
      onUpdate: function (k) { bloom.strength = base * (1 + 1.6 * Math.sin(Math.PI * Math.min(1, k * 1.25)) * (1 - k * 0.2)); },
      onDone: function () { bloom.strength = base; }, tag: 'deep' });
  }

  function light(names) { if (!inited) return; stars.setLit(names && names.length ? names : null); }
  function lineHover(info) {
    if (!inited || !rings) return;
    if (!info) { rings.setEmph(-1, -1); fx.setWedge(null); return; }
    var i = lineIdx && lineIdx[info.id] != null ? lineIdx[info.id] : -1, d = disc.desc(), it = d && i >= 0 ? d.items[i] : null;
    rings.setEmph(i, it ? it.mainIdx : -1);
    if (it) fx.setWedge({ a0: it.a0, a1: it.a1, r0: d.rIn * T.DISC_WEDGE.r0, r1: it.r, z1: it.z || 0, color: it.color || genHex(it.gen, it.kind) });
  }
  function setCursor(c, o) {
    if (!inited || !M) return;
    if (c == null) { rings.setCursor(-1); fx.setNeedle(null); fx.setWake(null); if (scale) scale.setCursor(null); return; }
    var A = g.CLSkyModel.angleAt, a = A(c + 0.5, M.nCh), k = Math.max(1, Math.round(M.nCh * 0.04));
    rings.setCursor((c + 0.5) / M.nCh); fx.setNeedle(a, !!(o && o.snap)); fx.setWake(A(Math.max(0, c + 0.5 - k), M.nCh), a);
    if (scale) scale.setCursor(c);
  }

  function captureHome() {
    if (!view || !S.camera || !S.controls) return;
    view.setHome({ p: S.camera.position.clone(), t: S.controls.target.clone() }); syncViews(); homeSet = true;
    if (cosmos) {
      var f = S.controls.target.clone().sub(S.camera.position).normalize();
      if (!homeDir || homeDir.dot(f) < 0.99995) { cosmos.reorient([f.x, f.y, f.z]); homeDir = f; }
      if (cosmosReady) cosmos.setState(mode === 'compass' ? 'dim' : 'show');
      applyReadingLight();
    }
  }
  function solid(now) {
    cosmosReady = true;
    if (now && !homeSet) captureHome();
    if (mode === 'constellation') neb.setState('show', now);
    if (cosmos && homeSet) cosmos.setState(mode === 'compass' ? 'dim' : 'show', now);
    applyReadingLight();
  }

  function init(ctx) {
    T = g.CLSkyTokens; S = ctx.scene; disc = ctx.disc; field = ctx.field; app = ctx.app; cards.setElement(ctx.card || null);
    if (inited || !T || !S || !g.THREE || !g.CLSkyMotion) return false;
    try {
      post = g.CLSkyPost.install(S);
      cosmos = g.CLSkyCosmos && g.CLSkyCosmosBake && g.CLSkyCosmosStars ? g.CLSkyCosmos.create({ scene: S }) : null;
      stars = g.CLSkyStars.create({ scene: S });
      trails = g.CLSkyTrails ? g.CLSkyTrails.create({ scene: S }) : null;
      neb = g.CLSkyNebula.create({ scene: S });
      bun = g.CLSkyBundles.create({ scene: S });
      var anchor = disc && disc.anchor ? disc.anchor() : null;
      rings = g.CLSkyRings.create({ scene: S, anchor: anchor });
      fx = g.CLSkyRingsFx.create({ scene: S, anchor: anchor });
      orb = g.CLSkyOrrery.create({ scene: S });
      sats = g.CLSkyOrrerySats && orb.rig ? g.CLSkyOrrerySats.create({ scene: S }) : null;
      view = g.CLSkyView.install({ scene: S, canvas: doc.getElementById('gl'), onChange: syncViews });
      rev = g.CLSkyReveal && g.CLSkyRevealGLSL ? g.CLSkyReveal.create({ scene: S }) : null;
    } catch (e) {
      if (g.console) console.warn('[sky-deep] 光层初始化失败，退回 SVG 读层', e);
      [post, cosmos, stars, trails, neb, bun, rings, fx, orb, sats, view, rev].forEach(function (m) { try { if (m && m.dispose) m.dispose(); } catch (e2) {} });
      post = cosmos = stars = trails = neb = bun = rings = fx = orb = sats = view = rev = null;
      return false;
    }
    inited = true;
    doc.body.classList.add('skd-gl');
    buildViews(ctx.hud);
    if (S.on) S.on('hover', onStarHover);
    if (field && field.on) field.on('hover', onCampHover);
    g.addEventListener('pointermove', cards.move, { passive: true });
    doc.addEventListener('pointerover', cards.axisOver); doc.addEventListener('pointerout', cards.axisOut);
    doc.addEventListener('focusin', cards.axisOver); doc.addEventListener('focusout', cards.axisOut);
    doc.addEventListener('pointerover', onSatSync); doc.addEventListener('pointerout', onSatSync);
    g.addEventListener('resize', function () {
      clearTimeout(homeT);
      homeT = setTimeout(function () { if (mode === 'compass') homeStale = true; else refreshHome(); }, 260);
    });
    var cv = doc.getElementById('gl');
    if (cv) cv.addEventListener('dblclick', function (e) { if (mode === 'compass' || !view) return; var hit = S.pick ? S.pick(e.clientX, e.clientY) : null; if (!hit) { view.reset(); syncViews(); } });
    return true;
  }
  function onGraph(model, graph, player) {
    if (!inited) return;
    if (rev) rev.finish();
    M = model; G = graph; mode = 'constellation'; hoverStar = null; hotCamp = null; hideCard(); cosmosReady = !rev; homeSet = false; homeDir = null;
    setStructure(false, true); mountStructure();
    dna = g.CLSkyDNA && G ? g.CLSkyDNA.of(G) : null;
    if (T.applyDNA) { T.applyDNA(dna); }
    if (neb.setDNA) { neb.setDNA(T.dna ? T.dna() : null); }
    counts(); buildStars(); buildField(); buildRings(); buildCosmos();
    if (cosmos && cosmos.setDefocus) cosmos.setDefocus(0);
    if (S.setBoost) S.setBoost(null, 'constellation');
    CLSkyMotion.cancelAll('deep');
    blur = T.BLUR.backdrop; post.setBlur(blur);
    rings.setState('backdrop'); fx.setState('hidden'); neb.setState(rev ? 'hidden' : 'show'); bun.setState('show'); starState('show'); orb.close();
    stars.setIgnite(0, true); rings.reveal(0);
    pendingReveal = function () {
      if (rev) rev.stage({ info: sky(), hero: heroKey, stars: stars, bun: bun, solid: solid });
      else igniteTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.ignite, ease: T.EASE.out, onUpdate: function (v) { stars.setIgnite(v); }, tag: 'deep' });
      revealTw = CLSkyMotion.tween({ from: 0, to: 1, dur: T.DUR.unfurl, delay: 0.6, ease: T.EASE.inOut, onUpdate: function (v) { rings.reveal(v); }, tag: 'deep' });
    };
    if (revealFallback) clearTimeout(revealFallback);
    revealFallback = setTimeout(reveal, 6000);
    homeTw = CLSkyMotion.seq([{ at: 1.9, fn: captureHome }], 'deep');
    if (player && g.CLSkyScale) {
      if (!scale) {
        var scrub = player.querySelector('input[type=range]'), wrap = mk('div', 'skd-scale');
        if (scrub) { scrub.parentNode.insertBefore(wrap, scrub); wrap.appendChild(scrub); scale = CLSkyScale.mount(wrap, {}); }
      }
      if (scale) scale.update({ nCh: M.nCh, mains: M.mains.map(function (m) { return { c0: m.c0, c1: m.c1, color: T.GEN[m.gen % T.GEN.length] }; }), density: M.density || [], keys: M.keyChapters || [] });
    }
    syncViews();
  }
  var pendingReveal = null, revealFallback = 0, homeT = 0, homeStale = false;
  function refreshHome() { homeStale = false; var h = app && app.atlas && app.atlas.home ? app.atlas.home() : null; if (h && view && G) view.setHome({ p: h.p, t: h.t }); }
  function reveal() {
    if (revealFallback) { clearTimeout(revealFallback); revealFallback = 0; }
    if (!pendingReveal) return false;
    var f = pendingReveal; pendingReveal = null; f(); return true;
  }
  function regroup() { if (!inited) return; liveUntil = now() + 3.2; }
  function readingDomOn() {
    var d = g.document; if (!d) return false;
    if (d.body && d.body.classList.contains('sky-decon-on')) return true;
    var ids = ['skyStoryPanel', 'skySearchPanel', 'skyEnrichPanel'];
    for (var i = 0; i < ids.length; i++) {
      var e = d.getElementById(ids[i]);
      if (e && !e.hidden && !e.classList.contains('skd-pm-out') && e.offsetHeight > 0) return true;
    }
    return false;
  }
  function frame(dt, tAnim, degrade) {
    if (!inited) return;
    clock += dt || 0;
    if (structureTw && reduced()) { CLSkyMotion.finishAll('structure'); structureTw = null; }
    setReading(readingDomOn());
    CLSkyMotion.tick(dt || 0);
    var tn = T.tierOf(degrade | 0);
    if (tn !== tierName) {
      tierName = tn; [cosmos, post, stars, trails, neb, bun, rings, fx, orb, sats, rev].forEach(function (m) { if (m && m.setTier) m.setTier(tn); });
      if (mode === 'compass') bindSats();
    }
    if (sky() !== skyRef && G) { buildStars(); buildField(); }
    if (disc && disc.rev && disc.rev() !== discRev && G) buildRings();
    var live = now() < liveUntil;
    var bg = S.core && S.core() && S.core().bgMat;
    if (bg && bg.uniforms.uPar && !reduced()) {
      var W = g.innerWidth || 1, H = g.innerHeight || 1, px = (pointer.x / W - 0.5) * 2, py = (pointer.y / H - 0.5) * -2, k = 1 - Math.exp(-(dt || 0) * 2.5);
      bg.uniforms.uPar.value.x += (px - bg.uniforms.uPar.value.x) * k; bg.uniforms.uPar.value.y += (py - bg.uniforms.uPar.value.y) * k;
    }
    if (cosmos) { cosmosFocus(); cosmos.update(dt, tAnim); }
    post.update(dt, tAnim); stars.update(dt, tAnim); if (trails) trails.update(dt, tAnim); neb.update(dt, tAnim, live); bun.update(dt, tAnim, live);
    rings.update(dt, tAnim); fx.update(dt, tAnim); orb.update(dt, tAnim); view.update(dt, tAnim);
    if (sats) sats.update(dt, tAnim, orb.stats().alpha);
    if (rev) rev.update(dt);
  }
  function stats() {
    if (!inited) return { inited: false };
    return { inited: true, mode: mode, reading: reading, structure: {on: structureOn, progress: structureProgress, moving: !!structureTw}, blur: +blur.toFixed(2), cosmos: cosmos ? cosmos.stats() : null, legacySky: S.core && S.core().legacySky ? S.core().legacySky() : null, post: post.stats(), stars: stars.stats(), trails: trails ? trails.stats() : null, nebula: neb.stats(), bundles: bun.stats(),
      rings: rings.stats(), fx: fx.stats(), orrery: orb.stats(), sats: sats ? sats.stats() : null, view: view.current(), tier: tierName, motion: CLSkyMotion.stats(), reveal: rev ? rev.stats() : null };
  }

  function prewarmCompass() {
    if (!inited || !g.CLSkyOrrery || !g.THREE) return null;
    var o = null, st = null;
    try {
      o = g.CLSkyOrrery.create({ scene: S });
      o.open({ center: new g.THREE.Vector3(0, 0, 0), radius: 1 });
      if (g.CLSkyOrrerySats && o.rig) { st = g.CLSkyOrrerySats.create({ scene: S }); st.set(o.rig(), [0, 1, 2].map(function (r) { return { ring: r, hex: T.C.BRASS, k: 1 }; })); }
    } catch (e) {}
    return function () { try { if (st) st.dispose(); } catch (e1) {} try { if (o) o.dispose(); } catch (e2) {} };
  }

  function layers() { return { cosmos: cosmos, post: post, stars: stars, trails: trails, neb: neb, bun: bun, rings: rings, fx: fx, orb: orb, sats: sats }; }

  g.CLSkyDeep = { init: init, onGraph: onGraph, dna: function () { return dna; }, reveal: reveal, frame: frame, setMode: setMode, light: light, lineHover: lineHover, setCursor: setCursor, regroup: regroup, prewarmCompass: prewarmCompass,
    layers: layers, setStructure: setStructure, finishStructure: finishStructure,
    readingFocus: readingFocus, clearReadingFocus: clearReadingFocus,
    lineCard: lineCard, resetView: function () { if (view && mode !== 'compass') view.reset(); syncViews(); }, captureHome: captureHome, stats: stats, enabled: function () { return inited; },
    hoverStar: function (name, quiet) { onStarHover(name ? { name: name } : null, !!quiet); return hoverStar; },
    hoverCamp: function (name, quiet) { var info = sky(), i = name ? sectorIndex(info, name) : -1; onCampHover(i >= 0 ? info.sectors[i] : null, !!quiet); return hotCamp; },
    setReading: setReading, reading: function () { return reading; }, setPlotHome: function (pose) { return !!(view && view.setHome && view.setHome(pose, 'plot')); },
    nudge: function (dAz, dPol) { if (!view || !view.nudge) return false; var r = view.nudge(dAz, dPol); syncViews(); return r; },
    preset: function (k) { if (!view || mode === 'compass') return false; var r = k === 'tour' ? view.tour(true) : view.preset(k); syncViews(); return r !== false; } };
})(window);
