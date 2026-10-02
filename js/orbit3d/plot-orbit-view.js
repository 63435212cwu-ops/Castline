/*! @role component · @owns js/orbit3d/plot-orbit-view.js · @budget dom_nodes<=400 draw_ms<=2 · @contract v46.1+v47
 * CLPlotOrbitViewFactory.create(scene,opts)->view (契约 §3.B)。
 * 几何仅 setTree/尺寸/车道变化时 renderGeometry；draw 按 camera.matrixWorld + 圆环 gg.matrixWorld
 * + W×H + mode/focus/hover/thread/char 签名门控。降级：低端档(cores<=4|body.dataset.tier==low) 与
 * prefers-reduced-motion 均不画光晕。不做 scene.setStage/setSearchSet/setStarTargets、卡片、键盘、CLTreeEvents。 */
(function (g) { 'use strict';
  var V = '46.1.1', MK = 0.972, BR0 = 0.918, BST = 0.058, R0 = 240, SEG = 72, ARC_STEP = 0.035, NS = 'http://www.w3.org/2000/svg';
  function se(t) { return document.createElementNS(NS, t); }
  function r2(v) { return Math.round(v * 100) / 100; }
  function r3(v) { return Math.round(v * 1000) / 1000; }
  function sc(c, n, o) { if (o) c.add(n); else c.remove(n); }
  function cv(e) { while (e && e.firstChild) e.removeChild(e.firstChild); }

  function create(scene, opts) {
    opts = opts || {};
    var strict = opts.strictTopology !== false;
    var body = document.body || document.documentElement;
    var low = (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4) || !!(body && body.dataset && body.dataset.tier === 'low');
    var rm = !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches);
    var halo = !low && !rm;

    var mode = 'constellation', tree = null, orbit = null, lay = empty(), focusEv = -1, hoverEv = -1,
      thread = null, charName = null, isEmpty = false, ring = null, ready = false, tried = false, builds = 0,
      lastSig = null, raf = 0, L = {}, cols = {};
    var tok = { tickL: 6, tickLM: 11, nodeR: 3.2, nodeRHot: 4.6, hair: 0.75, ringW: 1 };

    var root = document.createElement('div');
    root.id = 'clOrbit'; root.className = 'cl-orbit';
    root.setAttribute('data-mode', mode); root.setAttribute('data-focus', '0'); root.setAttribute('data-hover', '0');
    root.setAttribute('data-thread', ''); root.setAttribute('data-empty', '0'); root.setAttribute('aria-hidden', 'true');
    root.setAttribute('tabindex', '-1');
    var dial = se('svg'), evs = se('svg'), lab = document.createElement('div');
    dial.setAttribute('class', 'cl-orbit__dial'); dial.setAttribute('width', '100%'); dial.setAttribute('height', '100%');
    evs.setAttribute('class', 'cl-orbit__eventsvg'); evs.setAttribute('width', '100%'); evs.setAttribute('height', '100%');
    lab.className = 'cl-orbit__labels';
    root.appendChild(dial); root.appendChild(evs); root.appendChild(lab); body.appendChild(root);

    var ringEl = null, ticks = [], chaps = [], arcs = [], forks = [], nodes = [], lbls = [], links = [], spurs = [];

    function O() { return g.CLPlotOrbit; }
    function LANES() { return g.CLPlotOrbitLanes; }
    function Anchor() { return g.CLTreeAnchor; }
    function T3() { return g.THREE; }
    function grp() {
      var A = Anchor(); if (!A || typeof A.root !== 'function') return null;
      var r; try { r = A.root(); } catch (e) { return null; }
      return r && r.parent ? r.parent : null;
    }
    function uRout(m) {
      if (!m) return null;
      if (m.uniforms && m.uniforms.uRout && typeof m.uniforms.uRout.value === 'number') return m.uniforms.uRout.value;
      if (Object.prototype.toString.call(m) === '[object Array]') {
        var b = null; for (var i = 0; i < m.length; i++) { var v = uRout(m[i]); if (v !== null && (b === null || v > b)) b = v; } return b;
      }
      return null;
    }
    function findRing(p) {
      var b = null, bv = -Infinity;
      if (!p || typeof p.traverse !== 'function') return null;
      p.traverse(function (o) { var v = uRout(o && o.material); if (v !== null && v > bv) { bv = v; b = o; } });
      return b || null;
    }
    function info() { try { return (scene && typeof scene.camInfo === 'function') ? scene.camInfo() : null; } catch (e) { return null; } }
    function R() { return (orbit && orbit.frame && orbit.frame.R > 0) ? orbit.frame.R : R0; }

    function plane(x, y) {
      var q = grp(), T = T3();
      if (ring && ring.matrixWorld && T) {
        var v = new T.Vector3(x, y, 0); v.applyMatrix4(ring.matrixWorld);
        if (q && typeof q.worldToLocal === 'function') q.worldToLocal(v);
        return [v.x, v.y, v.z];
      }
      var ry = (orbit && orbit.frame && typeof orbit.frame.ry === 'number') ? orbit.frame.ry : 1;
      var pi = (orbit && orbit.frame && typeof orbit.frame.pitch === 'number') ? orbit.frame.pitch : 0;
      var yy = y * ry;
      return [x, yy * Math.cos(pi), -yy * Math.sin(pi)];
    }
    function scr(loc) {
      var T = T3(); if (!loc || !T || !scene || !scene.camera) return null;
      var v = new T.Vector3(loc[0], loc[1], loc[2]), q = grp();
      if (q && typeof q.localToWorld === 'function') q.localToWorld(v);
      v.project(scene.camera);
      var f = info(); if (!f || !f.W || !f.H) return null;
      return [(v.x * .5 + .5) * f.W, (-v.y * .5 + .5) * f.H];
    }
    function disk(r, a) { return scr(plane(r * Math.cos(a), r * Math.sin(a))); }
    function anchorLocal(ev, off) {
      var e = eventAt(ev); if (!e) return null;
      var dx = off ? off[0] : 0, dy = off ? off[1] : 0;
      return plane(e.r * Math.cos(e.angle) + dx, e.r * Math.sin(e.angle) + dy);
    }
    function anchorScreen(ev) { return scr(anchorLocal(ev)); }
    function starLocal(n) {
      if (!scene || typeof scene.nodeOf !== 'function') return null;
      try { var x = scene.nodeOf('c:' + n); return x && x.pos ? [x.pos.x, x.pos.y, x.pos.z] : null; } catch (e) { return null; }
    }

    function eventAt(ev) {
      var P = O(); if (P && typeof P.eventAt === 'function') { try { return P.eventAt(ev); } catch (e) {} }
      var e = (orbit && orbit.events) || []; for (var i = 0; i < e.length; i++) if (e[i].evIdx === ev) return e[i]; return null;
    }
    function threadAt(id) {
      var P = O(); if (P && typeof P.threadAt === 'function') { try { return P.threadAt(id); } catch (e) {} }
      var s = (orbit && orbit.lines) || []; for (var i = 0; i < s.length; i++) if (s[i].id === id) return s[i]; return null;
    }
    function orderList() {
      var a = ((orbit && orbit.events) || []).slice();
      a.sort(function (x, y) { return (x.order || 0) - (y.order || 0); });
      var o = []; for (var i = 0; i < a.length; i++) o.push(a[i].evIdx); return o;
    }
    function lineEvents(id) { var t = threadAt(id); return t && t.events ? t.events.slice() : []; }
    function participants(ev) {
      var o = [], s = {};
      function add(n) { if (n && !s[n]) { s[n] = 1; o.push(n); } }
      var er = orbit && orbit.eventRoles ? orbit.eventRoles[ev] : null;
      if (er) for (var i = 0; i < er.length; i++) add(er[i]);
      var e = eventAt(ev); if (e && e.cast) for (var j = 0; j < e.cast.length; j++) add(e.cast[j]);
      return o;
    }

    function empty() { return { R: 0, ry: 1, lanes: 0, laneOf: {}, radiusOf: {}, arcs: [], forks: [], chapters: [], ticks: [], crowded: false }; }
    function fbLayout() {
      var o = empty(); if (!orbit) return o;
      o.R = R(); o.ry = orbit.frame ? orbit.frame.ry : 1;
      var ls = orbit.lines || [], k = 0;
      for (var i = 0; i < ls.length; i++) {
        var l = ls[i], lane = l.kind === 'main' ? 0 : Math.max(1, l.depth || 1);
        o.laneOf[l.id] = lane;
        o.radiusOf[l.id] = lane === 0 ? R() * MK : R() * (BR0 - BST * (lane - 1));
        var p = (l.points || []).slice();
        o.arcs.push({ lineId: l.id, kind: l.kind, valid: l.status === 'confirmed' && !l.anchored, anchored: !!l.anchored,
          aStart: p.length ? p[0].angle : 0, aEnd: p.length ? p[p.length - 1].angle : 0, r: o.radiusOf[l.id], points: p });
        if (lane > k) k = lane;
      }
      o.lanes = k; return o;
    }
    function buildLay() {
      var A = LANES();
      if (A && typeof A.assign === 'function' && orbit) { try { var l = A.assign(orbit, tree, { strictTopology: strict }); if (l) return l; } catch (e) {} }
      return fbLayout();
    }
    function readTok() {
      try {
        var cs = g.getComputedStyle(root);
        function px(n, d) { var v = parseFloat(cs.getPropertyValue(n)); return isNaN(v) ? d : v; }
        tok = { tickL: px('--cl-orbit-tick-l', 6), tickLM: px('--cl-orbit-tick-l-major', 11), nodeR: px('--cl-orbit-node-r', 3.2), nodeRHot: px('--cl-orbit-node-r-hot', 4.6), hair: px('--cl-orbit-hair-w', .75), ringW: px('--cl-orbit-ring-w', 1) };
      } catch (e) {}
    }

    function pendMap() { var m = {}, a = (lay && lay.arcs) || []; for (var i = 0; i < a.length; i++) if (!a[i].valid) m[a[i].lineId] = 1; return m; }

    function renderGeometry() {
      cv(dial); cv(evs);
      var old = lab.querySelectorAll('.cl-orbit__linelabel');
      for (var z = 0; z < old.length; z++) lab.removeChild(old[z]);
      ticks = []; chaps = []; arcs = []; forks = []; nodes = []; lbls = []; links = []; spurs = [];
      readTok();
      ringEl = se('path'); ringEl.setAttribute('class', 'cl-orbit__ring--time'); ringEl.setAttribute('fill', 'none'); dial.appendChild(ringEl);
      var i, ts = (lay && lay.ticks) || [];
      for (i = 0; i < ts.length; i++) { var t = ts[i], el = se('line'); el.setAttribute('class', 'cl-orbit__tick'); el.setAttribute('data-ev', t.evIdx); el.setAttribute('data-chap', t.chapIdx); el.setAttribute('data-major', t.major ? '1' : '0'); dial.appendChild(el); ticks.push({ el: el, t: t }); }
      var ch = (lay && lay.chapters) || [];
      for (i = 0; i < ch.length; i++) { var tx = se('text'); tx.setAttribute('class', 'cl-orbit__chap'); tx.setAttribute('data-chap', ch[i].idx); tx.textContent = ch[i].name || ''; dial.appendChild(tx); chaps.push({ el: tx, c: ch[i] }); }
      var ar = (lay && lay.arcs) || [];
      for (i = 0; i < ar.length; i++) { var a = ar[i], pe = se('path'); pe.setAttribute('class', 'cl-orbit__arc'); pe.setAttribute('data-line-id', a.lineId); pe.setAttribute('data-kind', a.kind || ''); pe.setAttribute('data-valid', a.valid ? '1' : '0'); pe.setAttribute('data-lane', lay.laneOf[a.lineId] || 0); pe.setAttribute('fill', 'none'); dial.appendChild(pe); arcs.push({ el: pe, a: a, id: a.lineId }); }
      var fk = (lay && lay.forks) || [];
      for (i = 0; i < fk.length; i++) { var fl = se('line'); fl.setAttribute('class', 'cl-orbit__fork'); fl.setAttribute('data-line-id', fk[i].lineId); dial.appendChild(fl); forks.push({ el: fl, f: fk[i] }); }
      var pm = pendMap(), ev = (orbit && orbit.events) || [], hl = [];
      for (i = 0; i < ev.length; i++) { if (!halo) { hl.push(null); continue; } var h = se('circle'); h.setAttribute('class', 'cl-orbit__halo'); h.setAttribute('data-ev', ev[i].evIdx); evs.appendChild(h); hl.push(h); }
      for (i = 0; i < ev.length; i++) {
        var e = ev[i], ids = e.lineIds || [], pd = 0;
        for (var q = 0; q < ids.length; q++) if (pm[ids[q]]) { pd = 1; break; }
        var n = se('circle'); n.setAttribute('class', 'cl-orbit__node'); n.setAttribute('data-ev', e.evIdx); n.setAttribute('data-kind', e.kind || ''); n.setAttribute('data-chap', e.chapIdx); n.setAttribute('data-pending', pd ? '1' : '0'); n.setAttribute('tabindex', '0'); n.setAttribute('role', 'button'); n.setAttribute('aria-label', (e.title || '') + ' · ' + (e.chapter || ''));
        evs.appendChild(n); nodes.push({ el: n, halo: hl[i], ev: e.evIdx, lineIds: ids });
      }
      var ls = (orbit && orbit.lines) || [];
      for (i = 0; i < ls.length; i++) { var ln = ls[i], d = document.createElement('div'); d.className = 'cl-orbit__linelabel'; d.setAttribute('data-line-id', ln.id); d.setAttribute('data-kind', ln.kind || ''); d.setAttribute('data-valid', pm[ln.id] ? '0' : '1'); d.appendChild(document.createTextNode(ln.title || '')); if (pm[ln.id]) { var it = document.createElement('i'); it.textContent = '待校对'; d.appendChild(it); } lab.appendChild(d); lbls.push({ el: d, id: ln.id }); }
      rebuildFocus(); emit('geometry');
    }

    function rebuildFocus() {
      var i;
      for (i = 0; i < links.length; i++) if (links[i].el.parentNode) links[i].el.parentNode.removeChild(links[i].el);
      for (i = 0; i < spurs.length; i++) if (spurs[i].el.parentNode) spurs[i].el.parentNode.removeChild(spurs[i].el);
      links = []; spurs = [];
      if (focusEv < 0) return;
      var e = eventAt(focusEv); if (!e) return;
      var ids = e.lineIds || [];
      for (i = 0; i < ids.length; i++) { var l = se('line'); l.setAttribute('class', 'cl-orbit__link'); l.setAttribute('data-ev', focusEv); l.setAttribute('data-line-id', ids[i]); dial.appendChild(l); links.push({ el: l, id: ids[i] }); }
      var ps = participants(focusEv);
      for (i = 0; i < ps.length; i++) { var s = se('line'); s.setAttribute('class', 'cl-orbit__spur'); s.setAttribute('data-name', ps[i]); s.setAttribute('data-ev', focusEv); evs.appendChild(s); spurs.push({ el: s, name: ps[i] }); }
    }

    function apply() {
      root.setAttribute('data-mode', mode); root.setAttribute('data-focus', focusEv >= 0 ? '1' : '0');
      root.setAttribute('data-hover', hoverEv >= 0 ? '1' : '0'); root.setAttribute('data-thread', thread || '');
      root.setAttribute('data-empty', isEmpty ? '1' : '0'); root.setAttribute('aria-hidden', mode === 'constellation' ? 'true' : 'false');
    }
    function states() {
      var i;
      for (i = 0; i < nodes.length; i++) { var n = nodes[i], c = n.el.classList; sc(c, 'is-active', n.ev === focusEv); sc(c, 'is-hover', n.ev === hoverEv); sc(c, 'is-on', !!(thread && n.lineIds && n.lineIds.indexOf(thread) >= 0)); if (n.halo) sc(n.halo.classList, 'is-active', n.ev === focusEv); }
      for (i = 0; i < arcs.length; i++) sc(arcs[i].el.classList, 'is-active', !!(thread && arcs[i].id === thread));
      for (i = 0; i < lbls.length; i++) sc(lbls[i].el.classList, 'is-active', !!(thread && lbls[i].id === thread));
    }

    function matSig(m) { if (!m || !m.elements) return '-'; var e = m.elements, s = ''; for (var i = 0; i < 16; i++) s += r3(e[i]) + ','; return s; }
    function sig() {
      var q = grp(), f = info();
      return (scene && scene.camera ? matSig(scene.camera.matrixWorld) : '-') + '|' + (ring ? matSig(ring.matrixWorld) : (q ? matSig(q.matrixWorld) : '-')) + '|' + (f ? f.W : 0) + 'x' + (f ? f.H : 0) + '|' + mode + '|' + focusEv + '|' + hoverEv + '|' + (thread || '') + '|' + (charName || '');
    }
    function tickGeom(a, major, c) {
      var b = disk(R(), a); if (!b || !c) return null;
      var dx = b[0] - c[0], dy = b[1] - c[1], l = Math.sqrt(dx * dx + dy * dy) || 1; dx /= l; dy /= l;
      var n = major ? tok.tickLM : tok.tickL;
      return [b[0], b[1], b[0] + dx * n, b[1] + dy * n];
    }
    function midAngle(l) { var p = l.points || []; if (!p.length) return 0; return p.length === 1 ? p[0].angle : (p[0].angle + p[p.length - 1].angle) / 2; }

    function draw(force) {
      if (mode !== 'plot') return;
      var s = sig(); if (!force && s === lastSig) return; lastSig = s;
      var f = info(); if (!f || !f.W || !f.H || !T3() || !scene.camera) { emit('frame'); return; }
      var i, c = disk(R(), 0);
      if (ringEl && c) { var d = ''; for (i = 0; i <= SEG; i++) { var a = i / SEG * Math.PI * 2, p = disk(R(), a); if (!p) { d = ''; break; } d += (i ? 'L' : 'M') + r2(p[0]) + ',' + r2(p[1]); } ringEl.setAttribute('d', d ? d + 'Z' : ''); }
      for (i = 0; i < ticks.length; i++) { var tg = tickGeom(ticks[i].t.angle, ticks[i].t.major, c); if (!tg) continue; ticks[i].el.setAttribute('x1', r2(tg[0])); ticks[i].el.setAttribute('y1', r2(tg[1])); ticks[i].el.setAttribute('x2', r2(tg[2])); ticks[i].el.setAttribute('y2', r2(tg[3])); }
      for (i = 0; i < chaps.length; i++) { var b = disk(R(), chaps[i].c.aMid); if (!b || !c) continue; var dx = b[0] - c[0], dy = b[1] - c[1], l = Math.sqrt(dx * dx + dy * dy) || 1; dx /= l; dy /= l; var off = tok.tickLM + tok.tickL; chaps[i].el.setAttribute('x', r2(b[0] + dx * off)); chaps[i].el.setAttribute('y', r2(b[1] + dy * off)); }
      for (i = 0; i < arcs.length; i++) {
        var pts = arcs[i].a.points || [];
        if (!pts.length) { arcs[i].el.setAttribute('d', ''); continue; }
        if (pts.length === 1) { var s1 = disk(pts[0].r, pts[0].angle); arcs[i].el.setAttribute('d', s1 ? 'M' + r2(s1[0]) + ',' + r2(s1[1]) + 'h' + r2(tok.tickL) : ''); continue; }
        /* 弧必须贴着车道圆走：相邻事件之间按角度采样（每 ARC_STEP 弧度一段），不能画直线弦横穿盘心（v46.1 dpr2 实拍教训） */
        var dd = '', ra = arcs[i].a.r || pts[0].r, aS = pts[0].angle, aE = pts[pts.length - 1].angle, span = aE - aS;
        var nseg = Math.max(2, Math.ceil(Math.abs(span) / ARC_STEP));
        for (var j = 0; j <= nseg; j++) { var sp = disk(ra, aS + span * (j / nseg)); if (!sp) { dd = ''; break; } dd += (j ? 'L' : 'M') + r2(sp[0]) + ',' + r2(sp[1]); }
        arcs[i].el.setAttribute('d', dd);
      }
      for (i = 0; i < forks.length; i++) { var k = forks[i].f, p1 = disk(k.rFrom, k.angle), p2 = disk(k.rTo, k.angle); if (!p1 || !p2) continue; forks[i].el.setAttribute('x1', r2(p1[0])); forks[i].el.setAttribute('y1', r2(p1[1])); forks[i].el.setAttribute('x2', r2(p2[0])); forks[i].el.setAttribute('y2', r2(p2[1])); }
      for (i = 0; i < nodes.length; i++) { var nd = nodes[i], e = eventAt(nd.ev); if (!e) continue; var np = disk(e.r, e.angle); if (!np) continue; var rad = nd.ev === focusEv ? tok.nodeRHot : tok.nodeR; nd.el.setAttribute('cx', r2(np[0])); nd.el.setAttribute('cy', r2(np[1])); nd.el.setAttribute('r', r2(rad)); if (nd.halo) { nd.halo.setAttribute('cx', r2(np[0])); nd.halo.setAttribute('cy', r2(np[1])); nd.halo.setAttribute('r', r2(rad * 2.5)); } }
      for (i = 0; i < lbls.length; i++) { var t2 = threadAt(lbls[i].id); if (!t2) continue; var lp = disk((lay.radiusOf && lay.radiusOf[lbls[i].id]) || R() * MK, midAngle(t2)); if (!lp) continue; lbls[i].el.style.left = r2(lp[0]) + 'px'; lbls[i].el.style.top = r2(lp[1]) + 'px'; }
      drawFocus(); emit('frame');
    }
    function drawFocus() {
      if (focusEv < 0) return; var e = eventAt(focusEv); if (!e) return;
      var i, tgt = disk(e.r, e.angle);
      for (i = 0; i < links.length; i++) { var lr = lay.radiusOf && lay.radiusOf[links[i].id]; if (lr === undefined) continue; var a1 = disk(e.r, e.angle), a2 = disk(lr, e.angle); if (!a1 || !a2) continue; links[i].el.setAttribute('x1', r2(a1[0])); links[i].el.setAttribute('y1', r2(a1[1])); links[i].el.setAttribute('x2', r2(a2[0])); links[i].el.setAttribute('y2', r2(a2[1])); }
      for (i = 0; i < spurs.length; i++) { var from = scr(starLocal(spurs[i].name)) || anchorScreen(focusEv); if (!from || !tgt) continue; spurs[i].el.setAttribute('x1', r2(from[0])); spurs[i].el.setAttribute('y1', r2(from[1])); spurs[i].el.setAttribute('x2', r2(tgt[0])); spurs[i].el.setAttribute('y2', r2(tgt[1])); }
    }

    function on(t, fn) { (L[t] = L[t] || []).push(fn); return function () { off(t, fn); }; }
    function off(t, fn) { var a = L[t] || [], i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
    function emit(t, p) { var a = L[t]; if (!a || !a.length) return; a = a.slice(); for (var i = 0; i < a.length; i++) { try { a[i](p); } catch (e) {} } }

    function tryRim() {
      if (ready || tried) return; tried = true;
      var q = grp(); if (!q) { tried = false; return; }
      var r = findRing(q); if (!r) { tried = false; return; }
      ring = r; ready = true; if (tree) rebuild();
    }
    function rebuild() {
      var rr = R0;
      if (ready && ring && ring.material && ring.material.uniforms && ring.material.uniforms.uRout) { var v = ring.material.uniforms.uRout.value; if (typeof v === 'number' && v > 0) rr = v; }
      var P = O();
      if (P && typeof P.build === 'function') { try { var ob = P.build(tree, { rimR: rr, strictTopology: strict }); if (ob) { orbit = ob; builds++; } } catch (e) {} }
      lay = buildLay();
      isEmpty = !orbit || !(orbit.events && orbit.events.length) || !(orbit.lines && orbit.lines.length);
      renderGeometry(); apply(); states(); draw(true);
    }

    function loop() { raf = g.requestAnimationFrame(loop); if (mode !== 'plot') return; if (!ready) tryRim(); draw(false); }

    function setTree(t) { tree = t; rebuild(); return view; }
    function setMode(m) { m = m === 'plot' ? 'plot' : 'constellation'; if (m === mode) return mode; mode = m; apply(); if (mode === 'plot') { if (!ready) tryRim(); draw(true); } emit('mode', mode); return mode; }
    function toggle() { setMode(mode === 'plot' ? 'constellation' : 'plot'); return visible(); }
    function visible() { return mode === 'plot'; }
    function focusEvent(ev) { var v = (typeof ev === 'number' && ev >= 0) ? ev : -1; if (v === focusEv) return; focusEv = v; apply(); states(); rebuildFocus(); draw(true); emit('focus', focusEv); }
    function hoverEvent(ev) { var v = (typeof ev === 'number' && ev >= 0) ? ev : -1; if (v === hoverEv) return; hoverEv = v; apply(); states(); draw(true); emit('hover', hoverEv); }
    function focusThread(id) { var v = id || null; if (v === thread) return; thread = v; apply(); states(); draw(true); emit('thread', thread); }
    function setCharacter(n) { charName = n || null; draw(true); return charName; }
    function setEmpty(v) { isEmpty = !!v; apply(); return isEmpty; }
    function stats() { return { mode: mode, empty: isEmpty, nodes: nodes.length, arcs: arcs.length, forks: forks.length, chapters: chaps.length, focusEv: focusEv, hoverEv: hoverEv, thread: thread, lines: orbit && orbit.lines ? orbit.lines.length : 0, events: orbit && orbit.events ? orbit.events.length : 0, ok: !!orbit, R: R(), rimReady: ready, builds: builds }; }
    function state() { return { mode: mode, focusEv: focusEv, hoverEv: hoverEv, thread: thread, character: charName, empty: isEmpty, focus: focusEv, hover: hoverEv, visible: visible(), rimReady: ready }; }
    function layer(n) { return n === 'dial' ? dial : n === 'events' ? evs : n === 'labels' ? lab : root; }
    function destroy() { if (raf) { g.cancelAnimationFrame(raf); raf = 0; } if (root.parentNode) root.parentNode.removeChild(root); L = {}; tree = null; orbit = null; }

    var view = { setTree: setTree, setMode: setMode, toggle: toggle, visible: visible, focusEvent: focusEvent, focusThread: focusThread, hoverEvent: hoverEvent, setCharacter: setCharacter, setEmpty: setEmpty, stats: stats, state: state, eventAt: eventAt, threadAt: threadAt, layout: function () { return lay; }, orderList: orderList, lineEvents: lineEvents, participants: participants, anchorLocal: anchorLocal, anchorScreen: anchorScreen, screenOf: scr, layer: layer, on: on, off: off, destroy: destroy, version: V };
    apply(); raf = g.requestAnimationFrame(loop);
    return view;
  }

  g.CLPlotOrbitViewFactory = { name: 'CLPlotOrbitViewFactory', version: V, create: create };
})(typeof window !== 'undefined' ? window : this);
