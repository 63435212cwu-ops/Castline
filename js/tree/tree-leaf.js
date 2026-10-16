(function () {
  'use strict';

  var GOLD = 2.39996;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function str(v) { return v == null ? '' : String(v); }

  function vadd(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function vsub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function vmul(a, k) { return [a[0] * k, a[1] * k, a[2] * k]; }
  function vlen(a) { return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]); }
  function vnorm(a) { var L = vlen(a); return L > 1e-9 ? [a[0] / L, a[1] / L, a[2] / L] : [0, 1, 0]; }
  function vcross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function vdot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }

  var CACHE = null, CACHE_KEY = '', MS = {};

  function empty(reason) {
    return { ok: false, reason: reason, fp: '', leaves: [], byName: {}, byThread: {},
      stats: { leaves: 0, names: 0, dupNames: 0, maxPerName: 0, avgPerName: 0, onTrunk: 0, onBough: 0,
        spilled: 0, spillDY: -1, spillRr: -1, spillN: 0, loadMin: 0, loadMax: 0, loadUsed: 0, boughN: 0,
        ms: 0, fp: '', warn: [] } };
  }

  function assignLegacy(shape, tree, opts) {
    opts = opts || {};

    var key = 'L35|' + str(shape.fp) + '|' + str(tree.fp) + '|' + num(opts.maxLeaves, 900);
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var i, j, k, warn = [], maxLeaves = num(opts.maxLeaves, 900);
    var TH = tree.threads || [], segs = (shape.trunk && shape.trunk.segs) || [];
    var BOUGHS = shape.boughs || [], TAU2 = Math.PI * 2;
    function spillN(n) { return n <= 0 ? 0 : clamp(Math.round(n * 0.20), 2, 4); }

    var boughLoad = [], boughRoot = [], bi;
    for (bi = 0; bi < BOUGHS.length; bi++) {
      boughLoad.push(0);
      boughRoot.push((BOUGHS[bi].pts && BOUGHS[bi].pts.length) ? BOUGHS[bi].pts[0] : [0, 0, 0]);
    }
    function trunkPtAt(t) {
      var pts = (shape.trunk && shape.trunk.pts) || [];
      if (!pts.length) return [0, 0, 0];
      var u = clamp(t, 0, 1) * (pts.length - 1), a = Math.floor(u), b = Math.min(pts.length - 1, a + 1), f = u - a;
      return vadd(vmul(pts[a], 1 - f), vmul(pts[b], f));
    }
    function pickBough(p) {
      var best = 0, bestCost = 1e18, bestDY = 0, k2;
      var tgt = 2 + outN / Math.max(1, BOUGHS.length);
      for (k2 = 0; k2 < BOUGHS.length; k2++) {
        var dyy = Math.abs(p[1] - boughRoot[k2][1]);
        var over = boughLoad[k2] - tgt;
        var cost = dyy + (over > 0 ? over * over * 0.12 : 0);
        if (cost < bestCost) { bestCost = cost; bestDY = dyy; best = k2; }
      }
      var l0 = boughLoad[best];
      boughLoad[best] = l0 + 1;
      return { i: best, load: l0, dy: bestDY };
    }

    var hostOf = {}, mainIds = {};
    for (i = 0; i < segs.length; i++) mainIds[str(segs[i].threadId)] = segs[i];
    var trunkHost = { id: 'trunk', level: 0, pts: shape.trunk.pts, r: shape.trunk.r, az: 0 };
    for (i = 0; i < (shape.boughs || []).length; i++) hostOf[str(shape.boughs[i].threadId)] = shape.boughs[i];
    for (i = 0; i < (shape.limbs || []).length; i++) {
      var lm = shape.limbs[i], tid = str(lm.threadId);
      if (tid && !hostOf[tid]) hostOf[tid] = lm;
    }

    function leafPos(host, at, az, spread) {
      var pts = host.pts, rr = host.r;
      var hi = clamp(Math.round(at * (pts.length - 1)), 0, pts.length - 1);
      var base = pts[hi], rad0 = num(rr[hi], 0.01);
      var tan = vnorm(vsub(pts[Math.min(pts.length - 1, hi + 1)], pts[Math.max(0, hi - 1)]));
      var up = Math.abs(vdot(tan, [0, 1, 0])) > 0.99 ? [1, 0, 0] : [0, 1, 0];
      var U = vnorm(vcross(tan, up)), W = vnorm(vcross(tan, U));
      var nrm = vnorm(vadd(vmul(U, Math.cos(az)), vmul(W, Math.sin(az))));
      return { pos: vadd(base, vmul(nrm, Math.max(rad0 * 2.2, num(spread, 0)))), r: rad0 };
    }

    var trunkLeafTotal = 0;
    for (i = 0; i < TH.length; i++) {
      var t1 = TH[i] || {}, tid1 = str(t1.id), cs1 = t1.cast || [];
      if (!cs1.length) continue;
      var h1 = hostOf[tid1];
      if (mainIds[tid1] || num(t1.depth, 1) === 0) h1 = trunkHost;
      if (!h1) { h1 = hostOf[str(t1.parent)]; if (!h1) h1 = trunkHost; }
      if (h1 === trunkHost) {
        for (j = 0; j < cs1.length; j++) { if (str(cs1[j] && cs1[j].name)) trunkLeafTotal++; }
      }
    }

    var raw = [], onTrunk = 0, kTrunk = 0, outN = 0, spilled = 0, spillSum = 0, spillCnt = 0, rrSum = 0;
    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {}, tid2 = str(th.id), cast = th.cast || [];
      if (!cast.length) continue;
      var host = hostOf[tid2], hostKind = 1;
      if (mainIds[tid2] || num(th.depth, 1) === 0) { host = trunkHost; hostKind = 0; }
      if (!host) {
        host = hostOf[str(th.parent)];
        if (host) warn.push('线 ' + tid2 + ' 没有对应的枝，已挂到父线的枝上');
        else { host = trunkHost; hostKind = 0; warn.push('线 ' + tid2 + ' 没有对应的枝，已挂主干'); }
      }
      var hostLevel = host === trunkHost ? 0 : num(host.level, hostKind);
      var cs = cast.slice();
      cs.sort(function (a, b) {
        var d = num(b.w, 0) - num(a.w, 0);
        if (d) return d;
        return str(a.name) < str(b.name) ? -1 : (str(a.name) > str(b.name) ? 1 : 0);
      });
      var ord = {}, csT = cs.slice(), q2;
      csT.sort(function (a, b) {
        var ea = num(a.entry, -1), eb = num(b.entry, -1);
        if (ea < 0 && eb >= 0) return 1;
        if (eb < 0 && ea >= 0) return -1;
        if (ea !== eb) return ea - eb;
        return str(a.name) < str(b.name) ? -1 : (str(a.name) > str(b.name) ? 1 : 0);
      });
      for (q2 = 0; q2 < csT.length; q2++) ord[str(csT[q2].name)] = q2;
      var mainSeg = mainIds[tid2];
      var keepN = spillN(hostLevel === 0 ? cs.length : 0);
      for (j = 0; j < cs.length; j++) {
        var c = cs[j] || {}, nm = str(c.name);
        if (!nm) continue;
        var hUse = host, lvUse = hostLevel, lane = 0, pickDY = -1, rrDY = -1;
        var tIdx = ord[nm] != null ? ord[nm] : j;
        var dnm = Math.max(1, cs.length - 1);
        var s0 = mainSeg ? num(mainSeg.t0, 0.1) : 0.1, s1 = mainSeg ? num(mainSeg.t1, 1) : 0.9;
        var atT = clamp(s0 + (s1 - s0) * (cs.length === 1 ? 0.5 : 0.12 + 0.76 * (tIdx / dnm)), 0.02, 0.985);
        if (hostLevel === 0 && j >= keepN && BOUGHS.length) {
          var rri = outN++;
          var pOrig = trunkPtAt(atT);
          var pick = pickBough(pOrig);
          hUse = BOUGHS[pick.i];
          lvUse = 1;
          lane = pick.load;
          pickDY = pick.dy;
          var rrq = boughRoot[rri % BOUGHS.length];
          rrDY = Math.abs(pOrig[1] - rrq[1]);
        }
        var at2, az2;
        if (lvUse === 0) {
          at2 = atT;
          az2 = (kTrunk * GOLD) % TAU2;
        } else if (hUse !== host) {
          at2 = clamp(0.26 + 0.62 * ((lane % 5) / 4), 0.10, 0.94);
          az2 = (num(hUse.az, 0) + tIdx * GOLD) % TAU2;
        } else {
          at2 = cs.length === 1 ? 0.62 : 0.30 + 0.62 * (tIdx / dnm);
          az2 = (num(hUse.az, 0) + tIdx * GOLD) % TAU2;
        }
        var spread = lvUse === 0 ? (0.10 + 0.26 * (kTrunk / Math.max(1, trunkLeafTotal))) : 0;
        var lp = leafPos(hUse, at2, az2, spread);
        if (lvUse === 0) { onTrunk++; kTrunk++; } else if (hUse !== host) { spilled++; if (pickDY >= 0) { spillSum += pickDY; spillCnt++; rrSum += rrDY; } }
        raw.push({ key: tid2 + '|' + nm, name: nm, threadId: tid2, host: str(hUse.id) || 'trunk',
          hostLevel: lvUse, at: at2, az: az2, pos: lp.pos, pickDY: pickDY, rrDY: rrDY,
          n: num(c.n, 1), w: clamp(num(c.w, 0), 0, 1), lead: str(th.lead) === nm,
          main: !!mainIds[tid2] || num(th.depth, 1) === 0, dup: false, dupIdx: 0, dupOf: 0,
          entry: num(c.entry, -1), exit: num(c.exit, -1), camp: str(c.camp),
          color: num(th.color, 0xffb45c), spilled: lvUse === 1 && hUse !== host });
      }
    }

    if (raw.length > maxLeaves) {
      var seen = {}, keep = [], rest = [];
      var byW = raw.slice();
      byW.sort(function (a, b) { return num(b.w, 0) - num(a.w, 0) || (a.key < b.key ? -1 : 1); });
      for (i = 0; i < byW.length; i++) {
        if (!seen[byW[i].name]) { seen[byW[i].name] = 1; keep.push(byW[i]); }
        else rest.push(byW[i]);
      }
      var room = Math.max(0, maxLeaves - keep.length);
      warn.push('叶位截断：' + raw.length + ' → ' + Math.min(maxLeaves, keep.length + room) + '（每角色保底 1 片）');
      raw = keep.concat(rest.slice(0, room));
    }

    raw.sort(function (a, b) {
      if (a.threadId !== b.threadId) return a.threadId < b.threadId ? -1 : 1;
      var d = num(b.w, 0) - num(a.w, 0);
      if (d) return d;
      return a.key < b.key ? -1 : (a.key > b.key ? 1 : 0);
    });
    for (i = 0; i < raw.length; i++) raw[i].i = i;

    var byName = {}, byThread = {};
    for (i = 0; i < raw.length; i++) {
      var L = raw[i];
      (byName[L.name] = byName[L.name] || []).push(i);
      (byThread[L.threadId] = byThread[L.threadId] || []).push(i);
    }
    var names = 0, dupNames = 0, maxPer = 0, nm2;
    for (nm2 in byName) {
      if (!byName.hasOwnProperty(nm2)) continue;
      var arr = byName[nm2];
      arr.sort(function (a, b) { return num(raw[b].w, 0) - num(raw[a].w, 0) || (raw[a].key < raw[b].key ? -1 : 1); });
      for (k = 0; k < arr.length; k++) {
        raw[arr[k]].dupIdx = k;
        raw[arr[k]].dupOf = arr[0];
        raw[arr[k]].dup = arr.length > 1;
      }
      names++; if (arr.length > 1) dupNames++;
      if (arr.length > maxPer) maxPer = arr.length;
    }

    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var loadMin = 999, loadMax = -1, loadUsed = 0;
    for (i = 0; i < boughLoad.length; i++) {
      if (boughLoad[i] < loadMin) loadMin = boughLoad[i];
      if (boughLoad[i] > loadMax) loadMax = boughLoad[i];
      if (boughLoad[i] > 0) loadUsed++;
    }
    if (!boughLoad.length) { loadMin = 0; loadMax = 0; }
    var out = { ok: true, reason: '', fp: str(shape.fp), leaves: raw, byName: byName, byThread: byThread,
      stats: { leaves: raw.length, names: names, dupNames: dupNames, maxPerName: maxPer,
        avgPerName: names ? Math.round(raw.length / names * 100) / 100 : 0,
        onTrunk: onTrunk, onBough: raw.length - onTrunk,
        spilled: spilled, spillDY: spillCnt ? Math.round(spillSum / spillCnt * 10000) / 10000 : -1,
        spillRr: spillCnt ? Math.round(rrSum / spillCnt * 10000) / 10000 : -1,
        spillN: spillCnt, loadMin: loadMin, loadMax: loadMax, loadUsed: loadUsed,
        boughN: boughLoad.length, ms: MS[key], fp: str(shape.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  function posOf(x, path) {
    if (!x) return null;
    if (x.pos && x.pos.length >= 3 && isFinite(x.pos[0]) && isFinite(x.pos[1]) && isFinite(x.pos[2])) {
      return [x.pos[0], x.pos[1], x.pos[2]];
    }
    if (x.length >= 3 && isFinite(x[0]) && isFinite(x[1]) && isFinite(x[2])) {
      return [x[0], x[1], x[2]];
    }
    var t = isFinite(x) ? x : (isFinite(x.at) ? x.at : null);
    if (t != null && path && path.pts && path.pts.length) {
      var u = clamp(t, 0, 1) * (path.pts.length - 1), a = Math.floor(u),
          b = Math.min(path.pts.length - 1, a + 1), f = u - a;
      return vadd(vmul(path.pts[a], 1 - f), vmul(path.pts[b], f));
    }
    return null;
  }

  function pathOccurrence(path, evIdx) {
    if (!path) return null;
    var ep = path.eventPositions;
    if (ep && !ep.length && ep[evIdx]) {
      var q = posOf(ep[evIdx], path);
      if (q) return q;
    }
    var map = path.evPos;
    if (map && map[evIdx]) {
      var q2 = posOf(map[evIdx], path);
      if (q2) return q2;
    }
    if (ep && ep.length) {
      var evs = path.events || [], i;
      for (i = 0; i < evs.length; i++) {
        if (Math.floor(num(evs[i], -1)) !== evIdx) continue;
        var q3 = posOf(ep[i], path);
        if (q3) return q3;
      }
    }
    return null;
  }

  function anchorAt(shape, evIdx, path) {
    var occ = pathOccurrence(path, evIdx);
    if (occ) {
      return { pos: occ, host: (path && str(path.host)) || 'trunk', at: -1 };
    }
    var ea = shape && shape.eventAnchors && shape.eventAnchors[evIdx];
    if (ea && ea.pos && ea.pos.length >= 3 &&
        isFinite(ea.pos[0]) && isFinite(ea.pos[1]) && isFinite(ea.pos[2])) {
      return { pos: [ea.pos[0], ea.pos[1], ea.pos[2]],
        host: str(ea.host) || (path && str(path.host)) || 'trunk', at: num(ea.at, -1) };
    }
    return null;
  }

  function assignLogical(shape, tree, opts) {
    var maxLeaves = num(opts.maxLeaves, 900);
    var key = 'L45|' + str(shape.fp) + '|' + str(tree.fp) + '|' + maxLeaves;
    if (CACHE && CACHE_KEY === key) return CACHE;

    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    var warn = [], raw = [], i, j, q;
    var TP = shape.threadPaths || {}, TH = tree.threads || [], EV = tree.events || [];
    var evCast = {};
    function participates(evIdx, name) {
      var set = evCast[evIdx];
      if (!set) {
        set = evCast[evIdx] = {};
        var e = EV[evIdx], cs = (e && e.cast) || [];
        for (var z = 0; z < cs.length; z++) set[str(cs[z])] = 1;
      }
      return set[name] === 1;
    }

    for (i = 0; i < TH.length; i++) {
      var th = TH[i] || {}, tid = str(th.id), cast = th.cast || [];
      if (!cast.length) continue;
      var path = TP[tid];
      if (!path || !path.events || !path.events.length) {
        warn.push('线 ' + tid + ' 无 threadPaths，角色不落点（禁止 spill）');
        continue;
      }
      var isMain = (str(th.kind) === 'main' || num(th.depth, -1) === 0);
      for (j = 0; j < cast.length; j++) {
        var c = cast[j] || {}, nm = str(c.name);
        if (!nm) continue;
        var pickEv = -1, ap = null;
        for (q = 0; q < path.events.length; q++) {
          var evi = Math.floor(num(path.events[q], -1));
          if (evi < 0 || !participates(evi, nm)) continue;
          var cand = anchorAt(shape, evi, path);
          if (cand) { pickEv = evi; ap = cand; break; }
        }
        if (pickEv < 0 || !ap) {
          warn.push('角色 ' + nm + ' 在线 ' + tid + ' 无参与事件锚点，未落点');
          continue;
        }
        raw.push({
          key: tid + '|' + nm, name: nm, threadId: tid, host: str(ap.host) || 'trunk',
          hostLevel: isMain ? 0 : 1, at: num(ap.at, -1), az: 0, pos: ap.pos,
          pickDY: -1, rrDY: -1, n: num(c.n, 1),
          w: (typeof c.w === 'number' && isFinite(c.w)) ? clamp(c.w, 0, 1) : 0,
          lead: str(th.lead) === nm, main: isMain, dup: false, dupIdx: 0, dupOf: 0,
          entry: num(c.entry, -1), exit: num(c.exit, -1), camp: str(c.camp),
          color: num(th.color, 0xffb45c), spilled: false, evIdx: pickEv, logical: true
        });
      }
    }

    if (raw.length > maxLeaves) {
      var seen = {}, keep = [], rest = [];
      var byW = raw.slice();
      byW.sort(function (a, b) { return num(b.w, 0) - num(a.w, 0) || (a.key < b.key ? -1 : 1); });
      for (i = 0; i < byW.length; i++) {
        if (!seen[byW[i].name]) { seen[byW[i].name] = 1; keep.push(byW[i]); }
        else rest.push(byW[i]);
      }
      var room = Math.max(0, maxLeaves - keep.length);
      warn.push('叶位截断：' + raw.length + ' → ' + Math.min(maxLeaves, keep.length + room) + '（每角色保底 1 片）');
      raw = keep.concat(rest.slice(0, room));
    }

    raw.sort(function (a, b) {
      if (a.threadId !== b.threadId) return a.threadId < b.threadId ? -1 : 1;
      var d = num(b.w, 0) - num(a.w, 0);
      if (d) return d;
      return a.key < b.key ? -1 : (a.key > b.key ? 1 : 0);
    });
    for (i = 0; i < raw.length; i++) raw[i].i = i;

    var byName = {}, byThread = {};
    for (i = 0; i < raw.length; i++) {
      var L = raw[i];
      (byName[L.name] = byName[L.name] || []).push(i);
      (byThread[L.threadId] = byThread[L.threadId] || []).push(i);
    }
    var names = 0, dupNames = 0, maxPer = 0, nm2, k;
    for (nm2 in byName) {
      if (!byName.hasOwnProperty(nm2)) continue;
      var arr = byName[nm2];
      arr.sort(function (a, b) { return num(raw[b].w, 0) - num(raw[a].w, 0) || (raw[a].key < raw[b].key ? -1 : 1); });
      for (k = 0; k < arr.length; k++) {
        raw[arr[k]].dupIdx = k;
        raw[arr[k]].dupOf = arr[0];
        raw[arr[k]].dup = arr.length > 1;
      }
      names++; if (arr.length > 1) dupNames++;
      if (arr.length > maxPer) maxPer = arr.length;
    }

    var onTrunk = 0, onBough = 0;
    for (i = 0; i < raw.length; i++) { if (num(raw[i].hostLevel, 1) === 0) onTrunk++; else onBough++; }
    var boughN = 0;
    for (k in TP) { if (TP.hasOwnProperty(k)) boughN++; }
    var ms = Math.round(((window.performance && performance.now) ? performance.now() : Date.now()) - t0);
    if (MS[key] == null) MS[key] = ms;
    var out = { ok: true, reason: '', fp: str(shape.fp), logical: true,
      leaves: raw, byName: byName, byThread: byThread,
      stats: { leaves: raw.length, names: names, dupNames: dupNames, maxPerName: maxPer,
        avgPerName: names ? Math.round(raw.length / names * 100) / 100 : 0,
        onTrunk: onTrunk, onBough: onBough,
        spilled: 0, spillDY: -1, spillRr: -1, spillN: 0, loadMin: 0, loadMax: 0, loadUsed: 0,
        boughN: boughN, ms: MS[key], fp: str(shape.fp), warn: warn } };
    CACHE = out; CACHE_KEY = key;
    return out;
  }

  function assign(shape, tree, opts) {
    opts = opts || {};
    if (!shape || shape.ok !== true) return empty('no-shape');
    if (!tree || tree.ok !== true) return empty('no-tree');
    if (shape.logical === true) return assignLogical(shape, tree, opts);
    return assignLegacy(shape, tree, opts);
  }

  var API = {
    assign: assign,
    get: function () { return CACHE; },
    ofName: function (name) { return (CACHE && CACHE.byName[str(name)]) ? CACHE.byName[str(name)].slice() : []; },
    stats: function () { return CACHE ? CACHE.stats : { leaves: 0, ready: false }; }
  };
  window.CLTreeLeaf = API;
})();
