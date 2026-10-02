/**
 * @role component
 * @owns js/orbit3d/plot-orbit-lanes.js
 * @budget n/a (pure compute, O(n log n))
 * @contract v46.1+v47
 *
 * CLPlotOrbitLanes.assign(orbit, tree, opts) -> layout
 * Pure function, no DOM, no Math.random, no Date.
 * JS constants (naming = token, per contract 2):
 *   MAIN_K=0.972  BR0=0.918  BR_STEP=0.058  LANE_GAP=0.06  MAX_LANES=6
 *
 * Angle rule: time forward = angle decreasing, so aStart >= aEnd.
 * Branch lane reuse on lane k: prev.aEnd - LANE_GAP > cur.aStart.
 */
(function () {
  'use strict';

  var MAIN_K = 0.972;
  var BR0 = 0.918;
  var BR_STEP = 0.058;
  var LANE_GAP = 0.06;
  var MAX_LANES = 6;
  var VERSION = '46.1';

  function isArr(a) {
    return Object.prototype.toString.call(a) === '[object Array]';
  }

  function num(v, d) {
    return (typeof v === 'number' && isFinite(v)) ? v : d;
  }

  function pickStatus(t, line) {
    if (t && typeof t.topologyStatus === 'string') return t.topologyStatus;
    if (line && typeof line.status === 'string') return line.status;
    return 'pending';
  }

  function pickAnchored(t, line) {
    if (t && t.anchored === true) return true;
    if (t && t.anchored === false) return false;
    return !!(line && line.anchored === true);
  }

  function emptyLayout(orbit, opts) {
    var R = num(orbit && orbit.rings && orbit.rings.event && orbit.rings.event.r,
                num(orbit && orbit.frame && orbit.frame.R, num(opts && opts.rimR, 0)));
    var ry = num(orbit && orbit.frame && orbit.frame.ry, 1);
    return {
      R: R, ry: ry, lanes: 0, laneOf: {}, radiusOf: {},
      arcs: [], forks: [], chapters: [], ticks: [], crowded: false,
      warn: ['no-events']
    };
  }

  function assign(orbit, tree, opts) {
    opts = opts || {};
    if (!orbit || !isArr(orbit.events) || orbit.events.length === 0) {
      return emptyLayout(orbit, opts);
    }

    var warn = [];
    var R = num(orbit.rings && orbit.rings.event && orbit.rings.event.r,
                num(orbit.frame && orbit.frame.R, num(opts.rimR, 0)));
    var ry = num(orbit.frame && orbit.frame.ry, 1);

    var threadMap = {};
    var ti;
    if (tree && isArr(tree.threads)) {
      for (ti = 0; ti < tree.threads.length; ti++) {
        var th = tree.threads[ti];
        if (th && th.id != null) threadMap[th.id] = th;
      }
    }

    var evMap = {};
    var ei;
    for (ei = 0; ei < orbit.events.length; ei++) {
      var ev = orbit.events[ei];
      if (ev && ev.evIdx != null) evMap[ev.evIdx] = ev;
    }

    var lines = isArr(orbit.lines) ? orbit.lines : [];
    var meta = {};
    var mains = [];
    var branches = [];
    var i;

    for (i = 0; i < lines.length; i++) {
      var ln = lines[i];
      if (!ln || ln.id == null) continue;
      var t = threadMap[ln.id] || null;
      var kind = (ln.kind === 'main') ? 'main' : 'branch';
      var status = pickStatus(t, ln);
      var anchored = pickAnchored(t, ln);
      var srcEvents = isArr(ln.events) ? ln.events : [];
      var pts = [];
      var pi;
      for (pi = 0; pi < srcEvents.length; pi++) {
        var evIdx = srcEvents[pi];
        var node = evMap[evIdx];
        if (!node) { warn.push('missing-event:' + ln.id + ':' + evIdx); continue; }
        pts.push({ evIdx: evIdx, angle: num(node.angle, 0), r: 0 });
      }
      if (pts.length === 0) { warn.push('empty-line:' + ln.id); continue; }

      var aStart = -Infinity;
      var aEnd = Infinity;
      for (pi = 0; pi < pts.length; pi++) {
        var a = pts[pi].angle;
        if (a > aStart) aStart = a;
        if (a < aEnd) aEnd = a;
      }

      var o = {
        lineId: ln.id,
        kind: kind,
        valid: (status === 'confirmed') && !anchored,
        anchored: anchored,
        status: status,
        points: pts,
        aStart: aStart,
        aEnd: aEnd,
        parent: (ln.parent !== undefined) ? ln.parent : (t ? t.parent : null),
        attach: (ln.attach !== undefined) ? ln.attach : (t ? t.attach : null)
      };
      meta[ln.id] = o;
      if (kind === 'main') mains.push(o); else branches.push(o);
    }

    for (i = 0; i < mains.length; i++) {
      mains[i].k = 0;
      mains[i].r = R * MAIN_K;
    }

    branches.sort(function (x, y) {
      if (y.aStart !== x.aStart) return y.aStart - x.aStart;
      var ax = String(x.lineId);
      var ay = String(y.lineId);
      return ax < ay ? -1 : (ax > ay ? 1 : 0);
    });

    var laneLast = {};
    var laneCount = 0;
    var crowded = false;
    for (i = 0; i < branches.length; i++) {
      var c = branches[i];
      var k = -1;
      for (var lk = 1; lk <= laneCount; lk++) {
        if (laneLast[lk] - LANE_GAP > c.aStart) { k = lk; break; }
      }
      if (k === -1) {
        var nk = laneCount + 1;
        if (nk > MAX_LANES) { k = ((nk - 1) % MAX_LANES) + 1; crowded = true; }
        else { k = nk; laneCount = nk; }
      }
      laneLast[k] = c.aEnd;
      c.k = k;
      c.r = R * (BR0 - BR_STEP * (k - 1));
    }

    var laneOf = {};
    var radiusOf = {};
    var arcs = [];
    for (i = 0; i < lines.length; i++) {
      var id = lines[i] && lines[i].id;
      var m = (id != null) ? meta[id] : null;
      if (!m) continue;
      var pp;
      for (pp = 0; pp < m.points.length; pp++) m.points[pp].r = m.r;
      laneOf[id] = m.k;
      radiusOf[id] = m.r;
      arcs.push({
        lineId: id, kind: m.kind, valid: m.valid, anchored: m.anchored,
        aStart: m.aStart, aEnd: m.aEnd, r: m.r, points: m.points
      });
    }

    var forks = [];
    for (i = 0; i < arcs.length; i++) {
      var arc = arcs[i];
      if (arc.kind !== 'branch' || !arc.valid) continue;
      var src = meta[arc.lineId];
      var pid = src.parent;
      if (pid == null) continue;
      if (!Object.prototype.hasOwnProperty.call(radiusOf, pid)) {
        warn.push('orphan-parent:' + arc.lineId);
        continue;
      }
      var att = src.attach;
      if (att == null || !evMap[att]) {
        warn.push('missing-attach:' + arc.lineId);
        continue;
      }
      forks.push({
        lineId: arc.lineId, parentId: pid, evIdx: att,
        angle: num(evMap[att].angle, 0),
        rFrom: radiusOf[pid], rTo: radiusOf[arc.lineId]
      });
    }

    var chapMap = {};
    var chapOrder = [];
    for (ei = 0; ei < orbit.events.length; ei++) {
      var e2 = orbit.events[ei];
      var ck = (e2.chapIdx == null) ? '\u0000' : String(e2.chapIdx);
      var cg = chapMap[ck];
      if (!cg) {
        cg = chapMap[ck] = {
          idx: num(e2.chapIdx, -1), name: (e2.chapter != null ? e2.chapter : ''),
          n: 0, aStart: -Infinity, aEnd: Infinity,
          firstEv: null, firstAngle: -Infinity, lastEv: null, lastAngle: Infinity
        };
        chapOrder.push(ck);
      }
      var ang = num(e2.angle, 0);
      cg.n++;
      if (ang > cg.firstAngle) { cg.firstAngle = ang; cg.firstEv = e2.evIdx; }
      if (ang < cg.lastAngle) { cg.lastAngle = ang; cg.lastEv = e2.evIdx; }
      if (ang > cg.aStart) cg.aStart = ang;
      if (ang < cg.aEnd) cg.aEnd = ang;
    }

    var chapters = [];
    for (i = 0; i < chapOrder.length; i++) {
      var cc = chapMap[chapOrder[i]];
      chapters.push({
        idx: cc.idx, name: cc.name, n: cc.n,
        aStart: cc.aStart, aEnd: cc.aEnd,
        aMid: (cc.aStart + cc.aEnd) / 2,
        first: cc.firstEv, last: cc.lastEv
      });
    }
    chapters.sort(function (x, y) {
      if (x.idx !== y.idx) return x.idx - y.idx;
      var nx = String(x.name);
      var ny = String(y.name);
      return nx < ny ? -1 : (nx > ny ? 1 : 0);
    });

    var ticks = [];
    for (ei = 0; ei < orbit.events.length; ei++) {
      var e3 = orbit.events[ei];
      var tk = (e3.chapIdx == null) ? '\u0000' : String(e3.chapIdx);
      var tc = chapMap[tk];
      ticks.push({
        evIdx: e3.evIdx,
        angle: num(e3.angle, 0),
        chapIdx: num(e3.chapIdx, -1),
        major: !!(tc && tc.firstEv === e3.evIdx)
      });
    }
    ticks.sort(function (x, y) {
      if (y.angle !== x.angle) return y.angle - x.angle;
      return (x.evIdx < y.evIdx) ? -1 : (x.evIdx > y.evIdx ? 1 : 0);
    });

    return {
      R: R, ry: ry, lanes: laneCount,
      laneOf: laneOf, radiusOf: radiusOf,
      arcs: arcs, forks: forks, chapters: chapters, ticks: ticks,
      crowded: crowded, warn: warn
    };
  }

  var API = { name: 'CLPlotOrbitLanes', version: VERSION, assign: assign };
  try { window.CLPlotOrbitLanes = API; }
  catch (e) { if (typeof module !== 'undefined') module.exports = API; }
})();
