/**
 * @role component
 * @owns js/annulus/annulus-marks.js
 * @budget dom_nodes≤events+handoffs+24chords+orphans+beads; js_ms≤0.6
 * @contract v80
 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var name = 'marks';
  var version = 'v80';
  var S = {
    g: null,
    A: null,
    ticks: [],
    turns: [],
    handoffs: [],
    chords: [],
    orphanRing: null,
    orphanDots: [],
    beadSets: [],
    leadOnly: false,
    tickLen: 5,
    notch: 7,
    beadR: 9,
    beadRb: 7,
    beadRs: 6,
    layoutKey: null,
    layoutPasses: 0,
    frozenFrames: 0
  };
  function mk(tag, cls, parent) {
    var n = document.createElementNS(NS, tag);
    if (cls) n.setAttribute('class', cls);
    if (parent) parent.appendChild(n);
    return n;
  }

  function tok(n, fb) {
    try {
      var f = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(n));
      if (!isNaN(f) && f > 0) return f;
    } catch (e) {}
    return fb;
  }
  function degrade(ctx) {
    var red = !!(ctx && ctx.reduced);
    if (!red && window.matchMedia) {
      try { red = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
    }
    var low = !!(ctx && ctx.tier === 'low');
    if (!low && window.CLOrbit3DTier && window.CLOrbit3DTier.get) {
      try { low = window.CLOrbit3DTier.get() === 'low'; } catch (e2) {}
    }
    if (navigator.hardwareConcurrency <= 4) low = true;
    return red || low;
  }
  function proj(ctx, r, a) {
    if (ctx && typeof ctx.projectXY === 'function') return ctx.projectXY(r * Math.cos(a), r * Math.sin(a));
    var lay = window.CLOrbit3DLayer;
    if (!lay || !lay.localToGroup) return null;
    var loc = lay.localToGroup(r * Math.cos(a), r * Math.sin(a), 0);
    if (!loc) return null;
    var view = (ctx && ctx.view) || window.CLPlotOrbitView;
    if (view && view.screenOf) {
      var s = view.screenOf(loc);
      if (!s) return null;
      return [s[0], s[1]];
    }
    if (typeof loc.length === 'number') return [loc[0], loc[1]];
    return loc.x == null ? null : [loc.x, loc.y];
  }

  function tr(el, p) {
    el.setAttribute('transform', 'translate(' + p[0] + ' ' + p[1] + ')');
  }
  function dia(cx, cy, e) {
    var h = e / 2;
    return 'M' + (cx - h) + ' ' + cy + 'L' + cx + ' ' + (cy - h) +
      'L' + (cx + h) + ' ' + cy + 'L' + cx + ' ' + (cy + h) + 'Z';
  }
  function circ(cx, cy, r) {
    return 'M' + (cx - r) + ' ' + cy + 'A' + r + ' ' + r + ' 0 1 0 ' +
      (cx + r) + ' ' + cy + 'A' + r + ' ' + r + ' 0 1 0 ' + (cx - r) + ' ' + cy + 'Z';
  }
  function seg(x1, y1, x2, y2) {
    return 'M' + x1 + ' ' + y1 + 'L' + x2 + ' ' + y2;
  }
  function planeRing(ctx, r) {
    /* A disc-local circle becomes a perspective conic, not a screen circle.
     * Keep the guide and its orphan-event stars on exactly the same plane. */
    var d = '', p, i, n = 96;
    for (i = 0; i <= n; i++) {
      p = proj(ctx, r, i / n * Math.PI * 2);
      if (!p) return '';
      d += (i ? 'L' : 'M') + p[0].toFixed(2) + ' ' + p[1].toFixed(2);
    }
    return d + 'Z';
  }
  function ringOf(A, id) {
    if (id == null) return null;
    var rs = A.rings || [];
    for (var i = 0; i < rs.length; i++) {
      if (rs[i] && String(rs[i].id) === String(id)) return rs[i];
    }
    return null;
  }
  function finiteR(ring) {
    return !!ring && typeof ring.r === 'number' && isFinite(ring.r) && ring.valid !== false;
  }
  function idEq(x, y) {
    return x != null && y != null && String(x) === String(y);
  }
  function leadName(ring) {
    var r = ring.roster || {};
    if (r.lead) return String(r.lead);
    var l = ring.lead;
    if (l && typeof l === 'object') return l.known === false || !l.name ? '' : String(l.name);
    return l ? String(l) : '';
  }
  function clearG() {
    var g = S.g;
    if (g) while (g.firstChild) g.removeChild(g.firstChild);
    S.ticks = [];
    S.turns = [];
    S.handoffs = [];
    S.chords = [];
    S.orphanRing = null;
    S.orphanDots = [];
    S.beadSets = [];
    S.core = null;
    S.layoutKey = null;
    S.lastPlaced = [];
  }
  function hostOf(ctx) {
    if (!ctx) return null;
    if (ctx.groups && ctx.groups.marks) return ctx.groups.marks;   /* 主控：落进核心预留的 marks 分组，层叠位置正确 */
    return ctx.g || ctx.root || ctx.layer || ctx.marksGroup || ctx.svg;
  }
  function addBead(set, cls, text, r, parent, nameVal, lineId) {
    var tether = cls.indexOf('is-lead') >= 0 ? mk('path', 'cl-ann-bead-tether', parent) : null;
    if (tether) { tether.setAttribute('d', ''); tether.setAttribute('stroke', 'var(--cl-ann-gen-' + (set.gen == null ? 5 : set.gen) + ')'); }
    var bg = mk('g', cls, parent);
    if (lineId != null) bg.setAttribute('data-id', String(lineId));   /* 主控：珠也带线 id，悬停珠即悬停线 */
    if (set.gen != null) bg.setAttribute('data-gen', String(set.gen));
    var c = mk('circle', null, bg);
    c.setAttribute('r', String(r));
    var t = mk('text', null, bg);
    t.textContent = text.charAt(0) === '+' ? text : text.charAt(0);
    if (nameVal) bg.setAttribute('data-name', nameVal);
    set.beads.push({ g: bg, r: r, quiet: false, tether: tether, tetherPath: '' });
  }
  function build(ctx) {
    var A = ctx && ctx.A;
    var host = hostOf(ctx);
    if (!A || !A.ok || !host) return;
    S.leadOnly = degrade(ctx) || !!(ctx && ctx.far);   /* 主控：far LOD 只留领衔珠 */
    var farMode = !!(ctx && ctx.far);
    S.tickLen = tok('--cl-ann-tick-len', 5);
    S.notch = tok('--cl-ann-notch', 7);
    S.beadR = tok('--cl-ann-bead-r', 9);
    S.beadRs = tok('--cl-ann-bead-r-sm', 6);
    S.beadRb = tok('--cl-ann-bead-r-br', 7);

    if (!S.g || S.g.parentNode !== host) {
      if (S.g && S.g.parentNode) S.g.parentNode.removeChild(S.g);
      S.g = mk('g', 'cl-ann-marks', host);
    }
    clearG();
    S.A = A;
    var g = S.g;
    var rings = A.rings || [];
    var i, j, ring, evs, ev;
    var total = 0;
    for (i = 0; i < rings.length; i++) {
      if (!finiteR(rings[i])) continue;
      total += (rings[i].events || []).length;
    }
    var onlyTurn = (A.N || total) > 120;   /* 主控：阈值按全书事件数 N，不按各线事件之和（多线共享事件会虚高） */
    var gT = mk('g', 'cl-ann-ticks', g);
    var gU = mk('g', 'cl-ann-turns', g);
    var gH = mk('g', 'cl-ann-handoffs', g);
    var gC = mk('g', 'cl-ann-chords', g);
    var gO = mk('g', 'cl-ann-orphans', g);
    var gB = mk('g', 'cl-ann-beads', g);
    /* W1.5：盘心细环（0.18R / 0.34R），给空心一个结构，不承载信息 */
    S.core = [mk('path', 'cl-ann-core', gO), mk('path', 'cl-ann-core', gO)];

    for (i = 0; i < rings.length; i++) {
      ring = rings[i];
      if (!finiteR(ring)) continue;
      evs = ring.events || [];
      for (j = 0; j < evs.length; j++) {
        ev = evs[j];
        if (!ev || typeof ev.ang !== 'number') continue;
        if (ev.turn) {
          S.turns.push({ el: mk('path', 'cl-ann-turn', gU), r: ring.r, ang: ev.ang });
        } else if (!onlyTurn) {
          S.ticks.push({ el: mk('path', 'cl-ann-tick', gT), r: ring.r, ang: ev.ang });
        }
      }
    }
    var hs = A.handoffs || [];
    for (i = 0; i < hs.length; i++) {
      var h = hs[i];
      if (!h || typeof h.a !== 'number') continue;
      var hr = ringOf(A, h.toId);
      if (!finiteR(hr)) hr = ringOf(A, h.fromId);
      if (!finiteR(hr)) continue;
      var hp = mk('path', 'cl-ann-handoff is-hit', gH);
      hp.setAttribute('data-from', h.fromId == null ? '' : String(h.fromId));
      hp.setAttribute('data-to', h.toId == null ? '' : String(h.toId));
      S.handoffs.push({ el: hp, r: hr.r, a: h.a });
    }
    var cs = A.crossings || [];
    var cn = cs.length < (farMode ? 16 : 24) ? cs.length : (farMode ? 16 : 24);   /* far：共鸣辐条封顶 16，省 dom */
    for (i = 0; i < cn; i++) {
      var c = cs[i];
      if (!c || typeof c.ang !== 'number') continue;
      var ra = ringOf(A, c.a);
      var rb = ringOf(A, c.b);
      if (!finiteR(ra) || !finiteR(rb)) continue;
      var cp = mk('path', 'cl-ann-chord', gC);
      cp.setAttribute('data-a', c.a == null ? '' : String(c.a));
      cp.setAttribute('data-b', c.b == null ? '' : String(c.b));
      S.chords.push({ el: cp, a: c.a, b: c.b, ang: c.ang, ra: ra.r, rb: rb.r, hot: false });
    }
    var ors = A.orphans || [];
    if (ors.length) {
      S.orphanRing = mk('path', 'cl-ann-orphan-ring', gO);
      for (i = 0; i < ors.length; i++) {
        if (!ors[i] || typeof ors[i].ang !== 'number') continue;
        var od = mk('circle', 'cl-ann-orphan-dot', gO);
        od.setAttribute('r', String(S.tickLen / 2));
        S.orphanDots.push({ el: od, ang: ors[i].ang });
      }
    }
    for (i = 0; i < rings.length; i++) {
      ring = rings[i];
      if (!finiteR(ring)) continue;
      if (ring.kind !== 'main' && !(ring.eventCount >= (farMode ? 8 : 5))) continue;
      var ln = leadName(ring);
      if (!ln) continue;
      if (typeof ring.a1 !== 'number') continue;
      var set = { r: ring.r, a1: ring.a1, beads: [], gen: ring.gen, id: ring.id, main: ring.kind === 'main' };
      addBead(set, 'cl-ann-bead is-lead is-hit', ln, ring.kind === 'main' ? S.beadR : S.beadRb, gB, ln, ring.id);   /* W1.5：支线领衔珠小一号，相邻车道不相压 */
      if (!S.leadOnly) {
        var roster = ring.roster || {};
        var core = roster.core || [];
        var ncore = core.length < 3 ? core.length : 3;
        for (j = 0; j < ncore; j++) {
          if (!core[j]) continue;
          addBead(set, 'cl-ann-bead is-core is-hit', String(core[j]), S.beadRs, gB, String(core[j]), ring.id);
        }
        var more = roster.more | 0;
        if (more > 0) {
          addBead(set, 'cl-ann-bead is-more', '+' + more, S.beadRs, gB, null, ring.id);
        }
      }
      if (set.beads.length) S.beadSets.push(set);
    }
    frame(ctx);
  }
  function hitsPlaced(P, p, r) {
    for (var i = 0; i < P.length; i++) {
      var dx = P[i][0] - p[0], dy = P[i][1] - p[1], rr = P[i][2] + r + 9;   /* 珠组含文字外接盒，按圆心距留 9px 余量 */
      if (dx * dx + dy * dy < rr * rr) return true;
    }
    return false;
  }
  function linkBead(b, from, to) {
    if (!b.tether) return;
    var d = '', dx = to && from ? to[0] - from[0] : 0, dy = to && from ? to[1] - from[1] : 0;
    var length = Math.sqrt(dx * dx + dy * dy);
    if (!b.quiet && length > b.r + 3) {
      var k = (length - b.r - 1) / length;
      d = seg(from[0], from[1], from[0] + dx * k, from[1] + dy * k);
    }
    if (d !== b.tetherPath) { b.tether.setAttribute('d', d); b.tetherPath = d; }
  }
  function frame(ctx) {
    var A = S.A;
    if (!A || !S.g) return;
    var placed = [];   /* W1.5：已落位的可见珠（屏幕坐标+半径），后来者相撞则沿弧后退 */
    /* 珠优先落位；后执行的 labels 避让本帧珠，不用上帧标签反推珠位。 */
    if (ctx && ctx.A && ctx.A !== A) return;
    var nextKey = ctx && typeof ctx.geometryRevision === 'number' ?
      JSON.stringify([ctx.geometryRevision, ctx.hover, ctx.focus]) : null;
    if (nextKey !== null && nextKey === S.layoutKey) { S.frozenFrames++; return; }
    S.layoutKey = nextKey; S.layoutPasses++;
    var i, k, p, p2, e, b;
    var hl = S.tickLen / 2;
    for (i = 0; i < S.ticks.length; i++) {
      e = S.ticks[i];
      p = proj(ctx, e.r - hl, e.ang);
      p2 = proj(ctx, e.r + hl, e.ang);
      if (!p || !p2) continue;
      e.el.setAttribute('d', seg(p[0], p[1], p2[0], p2[1]));
    }
    for (i = 0; i < S.turns.length; i++) {
      e = S.turns[i];
      p = proj(ctx, e.r, e.ang);
      if (!p) continue;
      e.el.setAttribute('d', dia(p[0], p[1], S.tickLen));
    }
    for (i = 0; i < S.handoffs.length; i++) {
      e = S.handoffs[i];
      p = proj(ctx, e.r, e.a);
      if (!p) continue;
      var off = S.notch + hl;
      var da = e.r > 1 ? off / e.r : 0.04;
      var pl = proj(ctx, e.r, e.a + da);
      var pr = proj(ctx, e.r, e.a - da);
      if (!pl || !pr) continue;
      e.el.setAttribute('d',
        dia(pl[0], pl[1], S.tickLen) +
        dia(pr[0], pr[1], S.tickLen) +
        circ(p[0], p[1], S.notch));
    }
    var hv = ctx && ctx.hover;
    var fv = ctx && ctx.focus;
    for (i = 0; i < S.chords.length; i++) {
      e = S.chords[i];
      var hot = (hv != null && (idEq(hv, e.a) || idEq(hv, e.b))) ||
        (fv != null && (idEq(fv, e.a) || idEq(fv, e.b)));
      if (e.hot !== hot) { e.el.setAttribute('class', hot ? 'cl-ann-chord is-hot' : 'cl-ann-chord'); e.hot = hot; }
      p = proj(ctx, e.ra, e.ang);
      p2 = proj(ctx, e.rb, e.ang);
      if (!p || !p2) continue;
      e.el.setAttribute('d', seg(p[0], p[1], p2[0], p2[1]));
    }
    if (S.core) {
      var RR = isFinite(A.R) ? A.R : 0, ci;
      for (ci = 0; ci < 2; ci++) {
        S.core[ci].setAttribute('d', planeRing(ctx, RR * (ci ? 0.34 : 0.18)));
      }
    }
    if (S.orphanRing) {
      var R2 = (isFinite(A.R) ? A.R : 0) * 0.52;
      S.orphanRing.setAttribute('d', planeRing(ctx, R2));
      for (i = 0; i < S.orphanDots.length; i++) {
        e = S.orphanDots[i];
        p = proj(ctx, R2, e.ang);
        if (!p) continue;
        tr(e.el, p);
      }
    }
    for (i = 0; i < S.beadSets.length; i++) {
      var set = S.beadSets[i];
      if (!set.beads.length || typeof set.a1 !== 'number' || set.r <= 1) continue;
      /* 主控补丁：珠距按屏幕像素排（原版把像素半径当世界角度，珠全部叠在一起）；
       * 支线默认只留领衔珠，悬停/选中该线时核心珠才展开（盘面安静，信息在需要时出现） */
      var q0 = proj(ctx, set.r, set.a1), q1 = proj(ctx, set.r, set.a1 - 0.02);
      if (!q0 || !q1) continue;
      var pxPerRad = Math.sqrt((q1[0] - q0[0]) * (q1[0] - q0[0]) + (q1[1] - q0[1]) * (q1[1] - q0[1])) / 0.02;
      if (!(pxPerRad > 1)) continue;
      var lit = (hv != null && idEq(hv, set.id)) || (fv != null && idEq(fv, set.id));
      var cumPx = 0;   /* W1.5：领衔珠正坐弧头终点（像一枚端头结），核心珠沿弧向后（回溯时间）排开——不再悬到弧外与下一条主线/更替标签相撞 */
      for (k = 0; k < set.beads.length; k++) {
        b = set.beads[k];
        var quiet = !set.main && k > 0 && !lit;
        if (b.quiet !== quiet) { b.g.setAttribute('class', b.g.getAttribute('class').replace(/ is-quiet/g, '') + (quiet ? ' is-quiet' : '')); b.quiet = quiet; }
        if (k > 0) {
          var prr = set.beads[k - 1].r;
          cumPx += 2.9 * (b.r > prr ? b.r : prr);
        }
        var bp = proj(ctx, set.r, set.a1 + cumPx / pxPerRad);
        if (!bp) continue;
        if (!quiet) {
          /* 避让三段式：沿弧回溯 ≤12 步 → 越过弧头前进 ≤12 步 → 向外偏一小段半径再回溯（同车道拥挤时唯一出路） */
          var tries = 0, cand = null, rOff = 0, dir = 1, base = cumPx, hit = hitsPlaced(placed, bp, b.r);
          while (hit && tries < 36) {
            tries++;
            if (tries <= 12) { cumPx = base + 4 * tries; rOff = 0; }
            else if (tries <= 24) { cumPx = base - 4 * (tries - 12); rOff = 0; }
            else { cumPx = base + 4 * ((tries - 24) % 6); rOff = (1 + Math.floor((tries - 24) / 6) * 1.5) * (S.beadR + 6) / (pxPerRad / set.r); }   /* 外偏逐级加大（盘远端透视压缩，径向 1 世界单位只值 1–2 px） */
            cand = proj(ctx, set.r + rOff, set.a1 + cumPx / pxPerRad);
            if (!cand) continue;
            bp = cand; hit = hitsPlaced(placed, bp, b.r);
          }
          var accPx = cumPx, accR = rOff;   /* v90 F2：实际落点的弧向/径向位移（系绳长度判据用） */
          if (tries > 12) cumPx = base;   /* 前进/外偏不改变后续核心珠的回溯起点 */
          /* v90 F2（年轮清线）：支线领衔珠被挤离弧端过远（盘面位移 > 0.12R）时系绳必横穿他线——按既有规则让位 */
          if (!hit && !set.main && b.tether) {
            var aB = set.a1 + accPx / pxPerRad, rB = set.r + accR;
            var dxB = rB * Math.cos(aB) - set.r * Math.cos(set.a1), dyB = rB * Math.sin(aB) - set.r * Math.sin(set.a1);
            if (Math.sqrt(dxB * dxB + dyB * dyB) > 0.12 * (isFinite(A.R) && A.R > 0 ? A.R : set.r)) hit = true;
          }
          if (hit && !set.main) {   /* 36 步仍挤不下：支线珠让位（名字在账本里），主线珠永远保留 */
            if (!b.quiet) { b.g.setAttribute('class', b.g.getAttribute('class').replace(/ is-quiet/g, '') + ' is-quiet'); b.quiet = true; }
            linkBead(b, null, null);
            continue;
          }
          placed.push([bp[0], bp[1], b.r, String(set.id), k, tries]);
        }
        tr(b.g, bp);
        linkBead(b, q0, bp);
      }
    }
    S.lastPlaced = placed;
  }
  function destroy() {
    clearG();
    if (S.g && S.g.parentNode) S.g.parentNode.removeChild(S.g);
    S.g = null;
    S.A = null;
    S.layoutPasses = 0; S.frozenFrames = 0;
  }
  function stats() { return { layoutPasses: S.layoutPasses, frozenFrames: S.frozenFrames, beads: (S.lastPlaced || []).length }; }
  var plugin = {
    dbg: function () { return S.lastPlaced || []; },
    name: name,
    mount: build,
    refresh: build,
    frame: frame,
    update: frame,
    stats: stats,
    unmount: destroy,
    destroy: destroy
  };
  window.CLAnnulusMarks = {
    name: name,
    version: version,
    plugin: plugin,
    stats: stats
  };
  if (window.CLAnnulusSVG && typeof window.CLAnnulusSVG.use === 'function') {
    window.CLAnnulusSVG.use(plugin);
  }
})();
