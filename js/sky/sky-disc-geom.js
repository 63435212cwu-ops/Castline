(function (g) {
  'use strict';
  function create(C) {
    function samplesOf(r, a0, a1) {
      var n = Math.max(2, Math.ceil(Math.abs(a0 - a1) / C.STEP) + 1), out = [], i, z = C.zAt(r);
      for (i = 0; i < n; i++) { var a = a0 + (a1 - a0) * i / (n - 1); out.push([r * Math.cos(a), r * Math.sin(a), z]); }
      return out;
    }
    function pathOf(sm, reverse) {
      var d = '', i, p, any = false, n = sm.length;
      for (i = 0; i < n; i++) { var q = sm[reverse ? n - 1 - i : i]; p = C.proj(q[0], q[1], q[2]); if (!p) continue; d += (any ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); any = true; }
      return d;
    }
    function ptsOf(sm) { var out = [], i, p; for (i = 0; i < sm.length; i++) { p = C.proj(sm[i][0], sm[i][1], sm[i][2]); if (p) out.push(p); } return out; }
    function dOfPts(points) { var d = '', i; for (i = 0; i < points.length; i++) d += (i ? 'L' : 'M') + points[i][0].toFixed(1) + ' ' + points[i][1].toFixed(1); return d; }
    function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
    function grooveLanes(list) {
      var ends = [], lane = {};
      list.slice().sort(function (a, b) { return a.c0 - b.c0 || (b.c1 - b.c0) - (a.c1 - a.c0); }).forEach(function (l) {
        for (var k = 0; k < ends.length; k++) if (ends[k] + 1 < l.c0) { ends[k] = l.c1; lane[l.id] = k; return; }
        ends.push(l.c1); lane[l.id] = ends.length - 1;
      });
      return { n: ends.length, of: lane };
    }

    function chapterNos() {
      var M = C.M, n = M.nCh, prev = 0, out = [], c, v;
      for (c = 0; c < n; c++) {
        v = M.chapters[c] ? M.chapters[c].no : null;
        if (typeof v === 'number' && isFinite(v) && v >= 1 && v === Math.floor(v) && v >= prev) { out.push(v); prev = v; } else out.push(null);
      }
      return out;
    }
    function noOf(c) {
      var nos = C.geo && C.geo.nos, k;
      if (!nos || !nos.length) return c + 1;
      c = Math.max(0, Math.min(nos.length - 1, c | 0));
      for (k = c; k >= 0; k--) if (nos[k] != null) return nos[k];
      for (k = c + 1; k < nos.length; k++) if (nos[k] != null) return nos[k];
      return c + 1;
    }
    function ringText(line, kind) {
      var t = String(line.fullLabel || line.label || '');
      return kind === 'main' ? t.replace(/^全书阶段\s*\d+\s*[：:]\s*/, '') || t : t;
    }
    function splitText(t) {
      var n = t.length, best = -1, bd = Infinity, i;
      if (n < 8) return null;
      for (i = 2; i < n - 2; i++) if (/[，,、；;：:·—]/.test(t[i]) && Math.abs(i - n / 2) < bd) { bd = Math.abs(i - n / 2); best = i; }
      if (best > 0 && bd <= n * 0.3) return [t.slice(0, best), t.slice(best + 1)];
      best = Math.ceil(n / 2);
      return [t.slice(0, best), t.slice(best)];
    }
    function lanePlan() {
      var M = C.M, mainLane = {}, mEnd = [], k, i;
      M.mains.slice().sort(function (a, b) { return a.c0 - b.c0 || b.c1 - a.c1; }).forEach(function (m) {
        for (k = 0; k < mEnd.length; k++) if (mEnd[k] - m.c0 + 1 <= 1) break;
        if (k === mEnd.length && k >= 4) { k = 0; for (i = 1; i < mEnd.length; i++) if (mEnd[i] < mEnd[k]) k = i; }
        mEnd[k] = Math.max(mEnd[k] == null ? -1 : mEnd[k], m.c1); mainLane[String(m.id)] = k;
      });
      var named = M.lines.filter(function (l) { return l.named; }).sort(function (a, b) { return (a.rank || 0) - (b.rank || 0) || a.c0 - b.c0; });
      var spreadOf = {}, packedOf = {};
      named.forEach(function (l, j) { spreadOf[String(l.id)] = j; packedOf[String(l.id)] = l.lane || 0; });
      var K = C.P ? C.P.K : C.estimateK(), two = M.mains.some(function (m) {
        var t = ringText(m, 'main'), arc = (m.c1 - m.c0 + 1) / M.nCh * 2 * Math.PI * K * 0.86;
        return t.length * 15 + 18 > arc && !!splitText(t);
      });
      return { mainLane: mainLane, nm: Math.max(1, mEnd.length), spreadOf: spreadOf, nls: named.length, packedOf: packedOf, nlp: M.namedLanes || 0,
        gv: grooveLanes(M.lines.filter(function (l) { return !l.named; })), two: two };
    }

    function build() {
      C.rev++;
      [C.defs, C.gBezel, C.gDorm, C.gQuiet, C.gNamed, C.gMain, C.gDots, C.gHo, C.gLab, C.gCur, C.gTeth, C.gHit].forEach(clear);
      C.tethEls = []; if (C.tethGl) C.tethGl.set([], C.Wv, C.Hv);
      C.items = []; C.byId = {}; C.geo = null; C.prevKey = ''; C.dirty = true;
      C.builtGl = document.body.classList.contains('skd-gl');
      if (!C.M || !C.M.ok || !C.M.nCh) return;
      var L = lanePlan(), gv = L.gv, P = C.P, rq = [], rc = [], k;
      if (!P || P.nq !== gv.n || P.nls !== L.nls || P.nlp !== L.nlp || P.nm !== L.nm || P.two !== L.two) P = C.P = C.tune(P ? P.K : C.estimateK(), gv.n, L.nls, L.nlp, L.nm, L.two);
      var nl = P.nl, laneOf = P.spread ? L.spreadOf : L.packedOf, r = C.R_IN;
      for (k = 0; k < nl; k++) rc[k] = r - (k + 0.5) * P.wn;
      r -= nl * P.wn;
      var grooveOuter = r;
      if (gv.n && nl) r -= P.gap;
      for (k = 0; k < gv.n; k++) rq[k] = r - (k + 0.5) * P.wq;
      r -= gv.n * P.wq;
      var rMainIn = C.R_IN + P.mainGap, rMain = rMainIn + (L.nm - 1) * P.mainPitch, rBez = rMain + P.bez;
      C.geo = { rc: rc, rq: rq, rMain: rMain, rMainIn: rMainIn, mainLanes: L.nm, rBez: rBez, rNum: rBez + P.num, E: rBez + P.tail, rLo: Math.min(P.lo, r), lanesOuter: C.R_IN, grooveOuter: grooveOuter, grooveLane: gv.of };
      var ring = { el: C.mk('path', 'sd-ring', C.gBezel), sm: samplesOf(rBez, C.angle(0), C.angle(C.M.nCh)) };
      var step = [1, 2, 5, 10, 20, 25, 50, 100, 200].filter(function (s) { return C.M.nCh / s <= 12; })[0] || 500;
      var ticks = [], majors = [], nums = [], nos = chapterNos(), lastLab = -Infinity, lastC = 0;
      C.geo.nos = nos;
      for (var c = 0; c <= C.M.nCh; c++) {
        var no = c < C.M.nCh ? nos[c] : null, major = c === 0 || (no != null && !C.M.chapters[c].special && no % step === 0 && no > lastLab && nos[c - 1] !== no);
        (major ? majors : ticks).push({ a: C.angle(c), major: major });
        if (major && c < C.M.nCh) { var t = C.mk('text', 'sd-num', C.gBezel), lab = noOf(c); t.textContent = String(lab); lastLab = lab; lastC = c; nums.push({ el: t, a: C.angle(c + 0.5) }); }
      }
      var endNo = noOf(C.M.nCh - 1);
      if (endNo > lastLab && C.M.nCh - 1 - lastC >= Math.max(1, Math.round(step * 0.3))) { var te = C.mk('text', 'sd-num is-end', C.gBezel); te.textContent = String(endNo); nums.push({ el: te, a: C.angle(C.M.nCh - 0.5) }); }
      C.geo.ring = ring; C.geo.ticks = { el: C.mk('path', 'sd-tick', C.gBezel), list: ticks }; C.geo.majors = { el: C.mk('path', 'sd-tick is-major', C.gBezel), list: majors }; C.geo.nums = nums;
      C.geo.vols = ((C.M.axis && C.M.axis.volumes) || []).slice(1).map(function (v) { var t = C.mk('text', 'sd-vol', C.gBezel); t.textContent = v.label; return { el: t, a: C.angle(v.c) }; });
      C.geo.startMark = C.mk('path', 'sd-start', C.gBezel);
      C.geo.spokes = { el: C.mk('path', 'sd-spoke', C.gBezel), list: majors.map(function (t) { return t.a; }) };
      C.M.mains.forEach(function (m) { var ml = L.mainLane[String(m.id)] || 0; addItem(m, 'main', rMain - ml * P.mainPitch, 0.05, 0, ml); });
      C.geo.lanes = nl + gv.n;
      var cov = [];
      C.M.mains.forEach(function (m) { cov.push([m.c0, m.c1]); });
      cov.sort(function (a, b) { return a[0] - b[0]; });
      var gaps = [], cur = 0;
      cov.forEach(function (iv) { if (iv[0] > cur) gaps.push([cur, iv[0] - 1]); cur = Math.max(cur, iv[1] + 1); });
      if (cur < C.M.nCh) gaps.push([cur, C.M.nCh - 1]);
      C.geo.dorm = gaps.map(function (gp) { return { el: C.mk('path', 'sd-dormant', C.gDorm), sm: samplesOf(rMain, C.angle(gp[0] + 0.1), C.angle(gp[1] + 0.9)) }; });
      if (cov.length && cov[0][0] === 0 && cov[cov.length - 1][1] === C.M.nCh - 1 && C.M.nCh >= 6) {
        C.geo.dorm.push({ el: C.mk('path', 'sd-dormant', C.gDorm), sm: samplesOf(rMain, C.angle(C.M.nCh - 0.06), C.angle(0.06)) });
      }
      var maxN = C.M.lines.reduce(function (a, l) { return Math.max(a, l.named ? l.n : 0); }, 1);
      C.M.lines.forEach(function (l) {
        var rr = l.named ? rc[laneOf[String(l.id)] || 0] : rq[gv.of[l.id]];
        addItem(l, l.named ? 'named' : 'quiet', rr > 0 ? rr : C.geo.rLo + P.wq / 2, l.named ? 0.14 : 0.18, maxN);
      });
      C.geo.hos = C.M.handoffs.map(function (h) {
        var el = C.mk('path', 'sd-knot', C.gHo); el.setAttribute('data-from', h.from); el.setAttribute('data-to', h.to);
        var tt = C.mk('title', null, el); tt.textContent = (h.leadFrom ? h.leadFrom + ' → ' : '') + (h.leadTo || '') + (h.reason ? ' · ' + h.reason : '');
        var to = C.byId[h.to], a = to ? to.a0 : C.angle(h.c);
        return { el: el, a: a + 0.006, h: h };
      });
      C.geo.curMark = C.mk('path', 'sd-cur-mark', C.gCur); C.geo.curNum = C.mk('text', 'sd-cur-num', C.gCur);
      C.geo.comets = [];
      C.svg.setAttribute('data-lines', String(C.items.length));
    }
    function addItem(line, kind, r, pad, maxN, mainLane) {
      var a0 = C.angle(line.c0 + pad), a1 = C.angle(line.c1 + 1 - pad);
      var it = { id: String(line.id), line: line, kind: kind, r: r, a0: a0, a1: a1, sm: samplesOf(r, a0, a1), mainLane: mainLane || 0 };
      var host = kind === 'main' ? C.gMain : kind === 'named' ? C.gNamed : C.gQuiet;
      it.w = kind === 'main' ? (mainLane ? C.MAIN_SUB_W : C.MAIN_W) : kind === 'named' ? C.NAMED_W0 + C.NAMED_W1 * Math.sqrt(line.n / (maxN || 1)) : 1;
      if (kind === 'main' && mainLane) it.smLab = samplesOf(C.geo.rMain, a0, a1);
      it.el = null;
      if (!(C.builtGl && kind === 'quiet')) {
        it.el = C.mk('path', 'sd-arc is-' + kind + ' g' + line.gen + (line.resolved ? ' is-resolved' : '') + (line.suspended ? ' is-suspended' : ''), host);
        it.el.setAttribute('data-id', it.id);
        if (kind !== 'quiet') it.el.setAttribute('pathLength', '1');
        if (kind !== 'quiet') it.el.style.setProperty('--sd-w', it.w.toFixed(2) + 'px');
        it.el.style.setProperty('--sd-delay', (kind === 'main' ? line.c0 / C.M.nCh * 1.1 : 0.55 + line.c0 / C.M.nCh * 1.35).toFixed(3) + 's');
      }
      it.hit = C.mk('path', 'sd-hit', C.gHit); it.hit.setAttribute('data-id', it.id);
      if (kind !== 'quiet') {
        it.dots = line.events.map(function (ev) {
          var e = null;
          if (!C.builtGl) { e = C.mk('circle', 'sd-dot is-' + kind + ' g' + line.gen, C.gDots); e.setAttribute('r', kind === 'main' ? '1.5' : '1.1'); }
          return { el: e, a: C.angle(evSlot(ev) + 0.5) };
        });
        var id = 'sdlp-' + it.id.replace(/[^\w-]/g, '_');
        it.lp = C.mk('path', null, C.defs); it.lp.setAttribute('id', id);
        it.tx = C.mk('text', 'sd-label is-' + kind + ' g' + line.gen, C.gLab);
        var tp = C.mk('textPath', null, it.tx); tp.setAttribute('href', '#' + id); tp.setAttribute('startOffset', '50%');
        it.text = ringText(line, kind); tp.textContent = it.text;
        it.tp = tp; it.tw = 0; it.fh = 0;
        it.parts = kind === 'main' ? splitText(it.text) : null;
        if (it.parts) {
          it.lp2 = C.mk('path', null, C.defs); it.lp2.setAttribute('id', id + '-2');
          it.tp2 = C.mk('textPath', null, it.tx); it.tp2.setAttribute('href', '#' + id + '-2'); it.tp2.setAttribute('startOffset', '50%');
        }
      }
      C.items.push(it); C.byId[it.id] = it;
    }
    function evSlot(ev) {
      if (!C.evChIdx) { C.evChIdx = {}; C.M.chapterEvents.forEach(function (list, c) { list.forEach(function (i) { C.evChIdx[i] = c; }); }); }
      return C.evChIdx[ev] != null ? C.evChIdx[ev] : 0;
    }


    function descOf() {
      if (!C.M || !C.geo || !C.P) return null;
      var mainIdx = {};
      C.items.forEach(function (it, i) { if (it.kind === 'main') mainIdx[it.id] = i; });
      var list = C.items.map(function (it, i) {
        var l = it.line;
        return { id: it.id, kind: it.kind, r: it.r, z: C.zAt(it.r), a0: it.a0, a1: it.a1, w: it.w, gen: l.gen, c0: l.c0, c1: l.c1, lineIdx: i,
          mainIdx: it.kind === 'main' ? i : (l.mainId != null && mainIdx[String(l.mainId)] != null ? mainIdx[String(l.mainId)] : -1),
          resolved: !!l.resolved, suspended: !!l.suspended, beads: it.dots ? it.dots.map(function (o, k) { return { a: o.a, ev: l.events[k] }; }) : [] };
      });
      var bridges = [], caps = [];
      C.items.forEach(function (it) {
        var l = it.line;
        if (it.kind === 'named') {
          var par = (l.parent != null && C.byId[String(l.parent)]) || (l.mainId != null && C.byId[String(l.mainId)]) || null;
          if (par && par !== it) bridges.push({ a: it.a0, r0: it.r, r1: par.r, z0: C.zAt(it.r), z1: C.zAt(par.r), gen: l.gen });
        }
        if (it.kind !== 'quiet' && (l.resolved || l.suspended)) caps.push({ a: it.a1, r: it.r, z: C.zAt(it.r), kind: l.resolved ? 'resolved' : 'suspended', gen: l.gen });
      });
      return { nCh: C.M.nCh, angle0: C.angle(0), angle1: C.angle(C.M.nCh), rIn: C.geo.rLo, rLane: C.R_IN, rMain: C.geo.rMain,
        bowl: { r0: C.geo.rLo * 0.92, r1: C.geo.rMain, lift: C.LIFT }, rBez: C.geo.rBez, E: C.geo.E, zMain: C.zAt(C.geo.rMain), zBez: C.zAt(C.geo.rBez),
        tickLen: { major: C.P.tick, minor: C.P.tickMinor }, items: list, ticks: C.geo.ticks.list.concat(C.geo.majors.list), bridges: bridges, caps: caps, key: C.items.length + ':' + C.geo.rBez.toFixed(4) };
    }
    return { samplesOf: samplesOf, pathOf: pathOf, ptsOf: ptsOf, dOfPts: dOfPts, clear: clear, build: build, evSlot: evSlot, descOf: descOf, noOf: noOf };
  }
  g.CLSkyDiscGeom = { create: create };
})(window);
