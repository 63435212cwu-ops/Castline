(function () {
  'use strict';

  var NAME = 'orbit3d-geom';
  var VERSION = '47';
  var TAU = Math.PI * 2;
  var MERIDIAN = Math.PI / 2;

  var MAIN_K = 0.965;
  var BR0 = 0.905;
  var BR_STEP = 0.062;
  var FLOOR_K = 0.45;
  var GAP = 0.05;
  var VIS_LANES = 6;
  var WRAP_INSET = 0.34;
  var WRAP_MAX = 2;

  var FORK_MIN_SWEEP = 0.08;
  var FORK_K = 1 / 3;
  var MAX_SAMPLES = 4096;

  function isArr(v) { return Object.prototype.toString.call(v) === '[object Array]'; }
  function isObj(v) { return !!v && typeof v === 'object' && !isArr(v); }
  function num(v, d) { return (typeof v === 'number' && isFinite(v)) ? v : d; }
  function str(v) { return v == null ? '' : String(v); }
  function r6(v) { return Math.round(v * 1e6) / 1e6; }
  function cmpStr(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }

  function colorOf(v) {
    if (typeof v === 'number' && isFinite(v)) return Math.floor(v);
    if (typeof v === 'string' && v) {
      var s = v.charAt(0) === '#' ? v.slice(1) : (v.slice(0, 2).toLowerCase() === '0x' ? v.slice(2) : v);
      if (/^[0-9a-fA-F]{6}$/.test(s)) return parseInt(s, 16);
    }
    return null;
  }
  function paletteOf() {
    try { if (typeof window !== 'undefined' && window && window.CLPalette) return window.CLPalette; } catch (e) {}
    return null;
  }
  function kindColor(P, kind) {
    if (!P || typeof P.hex !== 'function') return null;
    var c = P.hex(kind);
    return (typeof c === 'number' && isFinite(c)) ? c : null;
  }
  function segColor(P, i, fallback) {
    if (P && typeof P.mainColor === 'function') {
      var c = P.mainColor(i);
      if (typeof c === 'number' && isFinite(c)) return c;
    }
    return fallback;
  }
  function isPending(status, anchored) {
    if (anchored === true) return true;
    return !!(status && status !== 'confirmed');
  }
  function angleFor(orderIndex, total) {
    var t = total > 0 ? (orderIndex / total) : 0;
    return r6(Math.PI / 2 - t * TAU + TAU);
  }
  function px(a, r) { return r * Math.cos(a); }
  function py(a, r) { return r * Math.sin(a); }

  function sampleArc(aStart, aEnd, r, step) {
    var a0 = num(aStart, 0), a1 = num(aEnd, 0), rr = num(r, 0);
    var st = Math.abs(num(step, 0.02));
    if (!(st > 0)) st = 0.02;
    var span = a0 - a1;
    var out = [];
    if (!(span > 0)) { out.push([px(a0, rr), py(a0, rr)]); out.push([px(a1, rr), py(a1, rr)]); return out; }
    var n = Math.ceil(span / st);
    if (n < 1) n = 1;
    if (n > MAX_SAMPLES) n = MAX_SAMPLES;
    for (var i = 0; i <= n; i++) {
      var a = a0 - span * (i / n);
      out.push([px(a, rr), py(a, rr)]);
    }
    return out;
  }
  function bezier(p0, c1, c2, p1, n) {
    var m = Math.floor(num(n, 16));
    if (!(m >= 1)) m = 1;
    if (m > MAX_SAMPLES) m = MAX_SAMPLES;
    var ax = num(p0 && p0[0], 0), ay = num(p0 && p0[1], 0);
    var bx = num(c1 && c1[0], 0), by = num(c1 && c1[1], 0);
    var cx = num(c2 && c2[0], 0), cy = num(c2 && c2[1], 0);
    var dx = num(p1 && p1[0], 0), dy = num(p1 && p1[1], 0);
    var out = [];
    for (var i = 0; i <= m; i++) {
      var t = i / m, u = 1 - t;
      var w0 = u * u * u, w1 = 3 * u * u * t, w2 = 3 * u * t * t, w3 = t * t * t;
      out.push([w0 * ax + w1 * bx + w2 * cx + w3 * dx, w0 * ay + w1 * by + w2 * cy + w3 * dy]);
    }
    return out;
  }

  function blank(R, ry, reason) {
    return {
      ok: false, version: VERSION, R: r6(R), ry: r6(ry),
      order: [], angleOf: {}, lanes: 0, laneR: [r6(R * MAIN_K)],
      arcs: [], forks: [], beads: [], handoffs: [],
      meridian: { angle: MERIDIAN }, pending: [], crowded: false,
      warn: [reason]
    };
  }

  function orderOf(tree, orbit, byEv, nEv, warn) {
    var i, cand, src;
    function take(list, key) {
      var seen = {}, out = [], j;
      for (j = 0; j < list.length; j++) {
        var v = list[j];
        var id = Math.floor(num(key ? num(v && v[key], num(v && v.i, -1)) : v, -1));
        if (id < 0 || !byEv[id] || seen[id]) return null;
        seen[id] = 1; out.push(id);
      }
      return out.length === nEv ? out : null;
    }
    if (orbit && isArr(orbit.events) && orbit.events.length) {
      cand = take(orbit.events, 'evIdx');
      if (cand) return { order: cand, src: 'orbit' };
      warn.push('orbit-order-partial');
    }
    if (tree.trunk && isArr(tree.trunk.events) && tree.trunk.events.length) {
      cand = take(tree.trunk.events, null);
      if (cand) return { order: cand, src: 'trunk' };
    }
    var all = [];
    for (var k in byEv) if (Object.prototype.hasOwnProperty.call(byEv, k)) all.push(byEv[k]);
    all.sort(function (a, b) {
      if (a.order !== b.order) return a.order - b.order;
      return a.evIdx - b.evIdx;
    });
    var out = [];
    for (i = 0; i < all.length; i++) out.push(all[i].evIdx);
    return { order: out, src: 'order' };
  }

  function cutSegments(tree, trunkSeq, posInTrunk, ownerMain, mainById, warn) {
    var segs = [], i;
    var hs = isArr(tree.handoffs) ? tree.handoffs : [];
    var cuts = [];
    for (i = 0; i < hs.length; i++) {
      var h = hs[i] || {};
      var at = Math.floor(num(h.at, -1));
      var p = (at >= 0 && posInTrunk[at] !== undefined) ? posInTrunk[at] : -1;
      if (p <= 0) { if (at >= 0 && p !== 0) warn.push('handoff-off-trunk:' + at); continue; }
      cuts.push({ p: p, at: at, from: str(h.from), to: str(h.to), kind: str(h.kind),
        reason: (typeof h.reason === 'string') ? h.reason : null,
        shared: isArr(h.shared) ? h.shared.slice(0) : null });
    }
    cuts.sort(function (a, b) { return a.p !== b.p ? a.p - b.p : cmpStr(a.at + '', b.at + ''); });
    var dedup = [], lastP = -1;
    for (i = 0; i < cuts.length; i++) {
      if (cuts[i].p === lastP) { warn.push('handoff-dup:' + cuts[i].at); continue; }
      lastP = cuts[i].p; dedup.push(cuts[i]);
    }
    cuts = dedup;
    if (!cuts.length && trunkSeq.length) {
      for (i = 1; i < trunkSeq.length; i++) {
        if (ownerMain[trunkSeq[i]] !== ownerMain[trunkSeq[i - 1]]) {
          cuts.push({ p: i, at: trunkSeq[i], from: str(ownerMain[trunkSeq[i - 1]]),
            to: str(ownerMain[trunkSeq[i]]), kind: '', reason: null, shared: null });
        }
      }
      if (cuts.length) warn.push('handoffs-empty-derived');
    }
    var bounds = [0];
    for (i = 0; i < cuts.length; i++) bounds.push(cuts[i].p);
    bounds.push(trunkSeq.length);
    for (i = 0; i + 1 < bounds.length; i++) {
      var a = bounds[i], b = bounds[i + 1];
      if (b <= a) continue;
      var lead = (i === 0) ? (cuts.length ? cuts[0].from : '') : cuts[i - 1].to;
      if (!lead || !mainById[lead]) {
        var guess = ownerMain[trunkSeq[a]];
        if (lead && !mainById[lead]) warn.push('handoff-unknown-line:' + lead);
        lead = guess ? guess : '';
      }
      segs.push({ lineId: lead, from: trunkSeq[a], to: trunkSeq[b - 1], n: b - a });
    }
    return { segs: segs, cuts: cuts };
  }

  function build(tree, opts) {
    opts = opts || {};
    var P = paletteOf();
    var orbit = (isObj(opts.orbit) && opts.orbit.ok !== false) ? opts.orbit : null;
    var R = num(opts.R, 0);
    if (!(R > 0) && orbit) R = num(orbit.frame && orbit.frame.R, 0);
    var ry = num(opts.ry, orbit ? num(orbit.frame && orbit.frame.ry, 1) : 1);
    var gap = num(opts.gap, GAP); if (!(gap >= 0)) gap = GAP;
    var maxLanes = Math.floor(num(opts.maxLanes, VIS_LANES)); if (!(maxLanes >= 1)) maxLanes = VIS_LANES;

    if (!(R > 0)) return blank(0, ry, 'no-radius');
    if (!isObj(tree) || tree.ok === false) return blank(R, ry, 'no-tree');
    var evs = isArr(tree.events) ? tree.events : [];
    var ths = isArr(tree.threads) ? tree.threads : [];
    if (!evs.length) return blank(R, ry, 'no-events');
    if (!ths.length) return blank(R, ry, 'no-threads');

    var warn = [], i, j, k;

    var byEv = {}, nEv = 0;
    for (i = 0; i < evs.length; i++) {
      var e = evs[i] || {};
      var id = Math.floor(num(e.i, i));
      if (id < 0 || byEv[id]) { warn.push('dup-event:' + id); continue; }
      byEv[id] = { evIdx: id, order: num(e.order, i + 1), kind: str(e.kind), w: num(e.w, 0) };
      nEv++;
    }
    if (!nEv) return blank(R, ry, 'no-events');

    var od = orderOf(tree, orbit, byEv, nEv, warn);
    var order = od.order;
    var angleOf = {};
    var orbAngle = {};
    if (od.src === 'orbit') {
      for (i = 0; i < orbit.events.length; i++) {
        var oe = orbit.events[i] || {};
        var oid = Math.floor(num(oe.evIdx, num(oe.i, -1)));
        if (oid >= 0) orbAngle[oid] = num(oe.angle, NaN);
      }
    }
    for (i = 0; i < order.length; i++) {
      var ev = order[i];
      var a = (od.src === 'orbit') ? orbAngle[ev] : NaN;
      angleOf[ev] = r6(num(a, angleFor(i, order.length)));
    }

    var recs = [], byId = {}, ownerCount = {};
    for (i = 0; i < ths.length; i++) {
      var t = ths[i] || {};
      var tid = str(t.id) || ('T' + i);
      if (byId[tid]) { warn.push('dup-line:' + tid); continue; }
      var raw = isArr(t.events) ? t.events : [];
      var clean = [], seenE = {};
      for (j = 0; j < raw.length; j++) {
        var q = Math.floor(num(raw[j], -1));
        if (q < 0 || seenE[q]) continue;
        if (!byEv[q]) { warn.push('missing-event:' + tid + ':' + q); continue; }
        seenE[q] = 1; clean.push(q);
      }
      if (!clean.length) { warn.push('empty-line:' + tid); continue; }
      var st = (typeof t.topologyStatus === 'string') ? t.topologyStatus : '';
      var anch = (t.anchored === true);
      var att = (t.attach == null) ? -1 : Math.floor(num(t.attach, -1));
      var rec = {
        id: tid, kind: (str(t.kind) === 'main') ? 'main' : 'branch', rawKind: str(t.kind),
        lead: str(t.lead), parent: (t.parent == null) ? '' : str(t.parent),
        attach: att >= 0 ? att : null, status: st, anchored: anch,
        valid: !isPending(st, anch),
        resolved: (t.resolved === true), suspended: (t.suspended === true),
        color: colorOf(t.color), heat: num(t.heat, 0), events: clean, lane: 0, r: 0
      };
      rec.aFirst = angleOf[clean[0]];
      rec.aLast = angleOf[clean[clean.length - 1]];
      rec.aStart = rec.aFirst; rec.aEnd = rec.aLast;
      if (rec.aFirst < rec.aLast) {
        warn.push('unsorted-line:' + tid);
        var aMax = -Infinity, aMin = Infinity;
        for (j = 0; j < clean.length; j++) {
          var ag = angleOf[clean[j]];
          if (ag > aMax) aMax = ag;
          if (ag < aMin) aMin = ag;
        }
        rec.aStart = aMax; rec.aEnd = aMin;
      }
      for (j = 0; j < clean.length; j++) ownerCount[clean[j]] = (ownerCount[clean[j]] || 0) + 1;
      recs.push(rec); byId[tid] = rec;
    }
    if (!recs.length) return blank(R, ry, 'no-threads');

    var branches = [], mains = [];
    for (i = 0; i < recs.length; i++) (recs[i].kind === 'main' ? mains : branches).push(recs[i]);
    branches.sort(function (x, y) {
      if (y.aStart !== x.aStart) return y.aStart - x.aStart;
      return cmpStr(String(x.id), String(y.id));
    });
    var laneLast = {}, laneCount = 0, crowded = false;
    for (i = 0; i < branches.length; i++) {
      var c = branches[i], lane = -1;
      for (k = 1; k <= laneCount; k++) {
        if (laneLast[k] - gap > c.aStart) { lane = k; break; }
      }
      if (lane === -1) { laneCount++; lane = laneCount; laneLast[lane] = Infinity; }
      laneLast[lane] = Math.min(laneLast[lane], c.aEnd);
      c.lane = lane;
    }
    var laneR = [r6(R * MAIN_K)], laneV = [0], laneM = [0];
    for (k = 1; k <= laneCount; k++) {
      var kv = ((k - 1) % maxLanes) + 1;
      var m = Math.floor((k - 1) / maxLanes);
      if (m > WRAP_MAX) m = WRAP_MAX;
      laneV.push(kv); laneM.push(m);
      laneR.push(r6(Math.max(R * FLOOR_K,
        R * (BR0 - BR_STEP * (kv - 1)) - R * BR_STEP * WRAP_INSET * m)));
      if (m > 0) crowded = true;
    }
    if (laneCount > maxLanes) warn.push('lanes-wrapped:' + (laneCount - maxLanes));
    for (i = 0; i < mains.length; i++) { mains[i].lane = 0; mains[i].r = laneR[0]; }
    for (i = 0; i < branches.length; i++) branches[i].r = laneR[branches[i].lane];

    var trunkSeq = [], posInTrunk = {}, ownerMain = {};
    for (i = 0; i < mains.length; i++) {
      for (j = 0; j < mains[i].events.length; j++) {
        if (ownerMain[mains[i].events[j]] === undefined) ownerMain[mains[i].events[j]] = mains[i].id;
      }
    }
    var trunkRaw = (tree.trunk && isArr(tree.trunk.events) && tree.trunk.events.length) ? tree.trunk.events : null;
    if (trunkRaw) {
      for (i = 0; i < trunkRaw.length; i++) {
        var tv = Math.floor(num(trunkRaw[i], -1));
        if (tv < 0 || !byEv[tv] || posInTrunk[tv] !== undefined) continue;
        posInTrunk[tv] = trunkSeq.length; trunkSeq.push(tv);
      }
    } else {
      var pool = [];
      for (i = 0; i < order.length; i++) if (ownerMain[order[i]] !== undefined) pool.push(order[i]);
      for (i = 0; i < pool.length; i++) { posInTrunk[pool[i]] = i; trunkSeq.push(pool[i]); }
    }
    var cut = cutSegments(tree, trunkSeq, posInTrunk, ownerMain, byId, warn);
    var segsByLine = {};
    for (i = 0; i < cut.segs.length; i++) {
      var sg = cut.segs[i];
      var host = byId[sg.lineId] && byId[sg.lineId].kind === 'main' ? byId[sg.lineId] : null;
      var fall = host ? host.color : null;
      var one = {
        aStart: angleOf[sg.from], aEnd: angleOf[sg.to],
        lead: host ? host.lead : '', color: segColor(P, i, fall)
      };
      if (!host) { warn.push('segment-no-line:' + sg.from); continue; }
      (segsByLine[host.id] = segsByLine[host.id] || []).push(one);
    }

    var arcs = [], byArc = {}, pending = [];
    for (i = 0; i < recs.length; i++) {
      var rc = recs[i];
      var segs = segsByLine[rc.id];
      if (rc.kind === 'main') {
        if (!segs || !segs.length) {
          segs = [{ aStart: rc.aStart, aEnd: rc.aEnd, lead: rc.lead, color: segColor(P, 0, rc.color) }];
          warn.push('main-no-segment:' + rc.id);
        }
      } else {
        segs = [{ aStart: rc.aStart, aEnd: rc.aEnd, lead: rc.lead, color: rc.color }];
      }
      var sw = Math.abs(rc.aStart - rc.aEnd);
      var arcLen = r6(sw * rc.r);
      var lenRatio = r6(Math.min(1, sw / TAU));
      var forkOrig = null;
      if (rc.kind !== 'main' && rc.parent) {
        forkOrig = {
          parent: rc.parent,
          attachEv: rc.attach,
          angle: (rc.attach != null && angleOf[rc.attach] !== undefined) ? angleOf[rc.attach] : null,
          r: (byId[rc.parent] ? byId[rc.parent].r : laneR[0])
        };
      }
      var arc = {
        lineId: rc.id, kind: rc.kind, lane: rc.lane, laneV: laneV[rc.lane], wrap: laneM[rc.lane],
        r: rc.r, crowded: laneM[rc.lane] > 0,
        aStart: rc.aStart, aEnd: rc.aEnd, sweep: r6(sw),
        arcLength: arcLen, lengthRatio: lenRatio, forkOrigin: forkOrig,
        valid: rc.valid, anchored: rc.anchored, status: rc.status,
        resolved: rc.resolved, suspended: rc.suspended,
        color: (rc.kind === 'main') ? segs[0].color : rc.color,
        heat: rc.heat, len: rc.events.length, lead: rc.lead,
        beads: rc.events.slice(0), segments: segs
      };
      arcs.push(arc); byArc[rc.id] = arc;
      if (!rc.valid) pending.push(rc.id);
    }

    var beads = [];
    for (i = 0; i < recs.length; i++) {
      var rb = recs[i];
      for (j = 0; j < rb.events.length; j++) {
        var bv = rb.events[j], be = byEv[bv];
        beads.push({
          evIdx: bv, lineId: rb.id, angle: angleOf[bv], r: rb.r, w: be.w,
          kind: be.kind, color: kindColor(P, be.kind),
          owners: (ownerCount[bv] || 0), shared: (ownerCount[bv] || 0) > 1,
          first: j === 0, last: j === rb.events.length - 1
        });
      }
    }

    var forks = [];
    for (i = 0; i < recs.length; i++) {
      var rf = recs[i];
      if (rf.kind === 'main' || !rf.valid) continue;
      if (!rf.parent) { warn.push('no-parent:' + rf.id); continue; }
      var par = byId[rf.parent];
      if (!par) { warn.push('orphan-parent:' + rf.id); continue; }
      if (rf.attach == null || !byEv[rf.attach]) { warn.push('missing-attach:' + rf.id); continue; }
      var a0 = angleOf[rf.attach], r0 = par.r;
      var a1 = rf.aFirst, r1 = rf.r;
      var sweep = a0 - a1;
      if (sweep < 0) warn.push('fork-backwards:' + rf.id);
      if (!(sweep > FORK_MIN_SWEEP)) sweep = FORK_MIN_SWEEP;
      var L0 = r0 * sweep * FORK_K, L1 = r1 * sweep * FORK_K;
      var c1x = px(a0, r0) + L0 * Math.sin(a0), c1y = py(a0, r0) - L0 * Math.cos(a0);
      var c2x = px(a1, r1) - L1 * Math.sin(a1), c2y = py(a1, r1) + L1 * Math.cos(a1);
      forks.push({
        lineId: rf.id, parentId: par.id, evIdx: rf.attach, angle: a0,
        rFrom: r0, rTo: r1, ctrl: [[r6(c1x), r6(c1y)], [r6(c2x), r6(c2y)]]
      });
    }

    var handoffs = [];
    for (i = 0; i < cut.cuts.length; i++) {
      var cu = cut.cuts[i];
      handoffs.push({
        evIdx: cu.at, angle: angleOf[cu.at], r: laneR[0],
        from: cu.from, to: cu.to, kind: cu.kind,
        reason: cu.reason, shared: cu.shared
      });
    }

    var firstEv = (trunkSeq.length ? trunkSeq[0] : (order.length ? order[0] : 0));
    var firstAngle = (angleOf[firstEv] !== undefined) ? angleOf[firstEv] : MERIDIAN;
    var mainR = laneR[0];
    var genesis = {
      evIdx: firstEv,
      angle: r6(firstAngle),
      r: r6(mainR),
      x: r6(px(firstAngle, mainR)),
      y: r6(py(firstAngle, mainR)),
      lead: (recs.length && recs[0].kind === 'main') ? recs[0].lead : '',
      label: '主线起点 · 纪元启航'
    };

    var epochs = [];
    var epochNames = ['纪元破晓 · 启航发端', '风云际会 · 剧情推进', '风暴前夕 · 矛盾激化', '巅峰对决 · 命运高潮', '万流归海 · 纪元收束'];
    var nTrunk = trunkSeq.length || order.length || 1;
    var nEpochs = Math.min(5, Math.max(3, Math.floor(nTrunk / 6) + 1));
    for (var ep = 0; ep < nEpochs; ep++) {
      var idxInTrunk = Math.min(nTrunk - 1, Math.floor(ep * (nTrunk - 1) / Math.max(1, nEpochs - 1)));
      var epEv = trunkSeq.length ? trunkSeq[idxInTrunk] : order[idxInTrunk];
      var epAng = (angleOf[epEv] !== undefined) ? angleOf[epEv] : (MERIDIAN - (ep / nEpochs) * TAU);
      epochs.push({
        epochIdx: ep + 1,
        title: epochNames[ep] || ('纪元阶段 · 第 ' + (ep + 1) + ' 幕'),
        evIdx: epEv,
        angle: r6(epAng),
        r: r6(mainR),
        ratio: r6(ep / Math.max(1, nEpochs - 1))
      });
    }

    return {
      ok: true, version: VERSION, R: r6(R), ry: r6(ry),
      order: order, angleOf: angleOf,
      lanes: laneCount, laneR: laneR,
      arcs: arcs, forks: forks, beads: beads, handoffs: handoffs,
      genesis: genesis, epochs: epochs,
      meridian: { angle: MERIDIAN },
      pending: pending, crowded: crowded, warn: warn
    };
  }

  function stats(desc) {
    var d = isObj(desc) ? desc : null;
    return {
      arcs: d && isArr(d.arcs) ? d.arcs.length : 0,
      forks: d && isArr(d.forks) ? d.forks.length : 0,
      beads: d && isArr(d.beads) ? d.beads.length : 0,
      handoffs: d && isArr(d.handoffs) ? d.handoffs.length : 0,
      pending: d && isArr(d.pending) ? d.pending.length : 0,
      lanes: d ? num(d.lanes, 0) : 0,
      crowded: !!(d && d.crowded)
    };
  }

  var API = {
    name: NAME, version: VERSION,
    build: build, stats: stats, sampleArc: sampleArc, bezier: bezier
  };
  try { window.CLOrbit3DGeom = API; }
  catch (e) { if (typeof module !== 'undefined' && module.exports) module.exports = API; }
})();
