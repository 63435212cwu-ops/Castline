(function () {
  'use strict';

  var GOLD = 2.39996;
  var TAU = Math.PI * 2;
  var COLOR_DEFAULT = 0xffb45c;

  var cache = {};
  var last = null;

  function clamp(v, lo, hi) {
    return v < lo ? lo : (v > hi ? hi : v);
  }

  function num(v, fallback) {
    return (typeof v === 'number' && v === v) ? v : fallback;
  }

  function pickSide(events, at, after) {
    var out = [];
    if (!events || !events.length) return out;
    for (var k = 0; k < events.length; k++) {
      var e = events[k];
      if (typeof e !== 'number') continue;
      if (after ? e > at : e < at) out.push(e);
    }
    out.sort(function (a, b) { return a - b; });
    return out;
  }

  function findThread(threads, id) {
    if (!threads || !threads.length || !id) return null;
    for (var k = 0; k < threads.length; k++) {
      if (threads[k] && threads[k].id === id) return threads[k];
    }
    return null;
  }

  function segColor(seg) {
    if (seg && typeof seg.color === 'number' && seg.color === seg.color) return seg.color;
    return COLOR_DEFAULT;
  }

  function fail(reason) {
    var res = {
      ok: false,
      reason: reason,
      fp: '',
      forks: [],
      warn: [],
      stats: { forks: 0, born: 0, promoted: 0, ms: 0, fp: '', ok: false }
    };
    last = res;
    return res;
  }

  function compute(tree) {
    if (!tree || tree.ok !== true) return fail('no-tree');
    var hs = tree.handoffs;
    if (!hs || !hs.length) return fail('no-handoff');

    var fp = (typeof tree.fp === 'string' && tree.fp) ? tree.fp : String(tree.fp || '');
    if (fp && Object.prototype.hasOwnProperty.call(cache, fp)) return cache[fp];

    var started = Date.now();
    var warn = [];
    var trunk = tree.trunk || {};
    var segs = trunk.segments || [];
    var hsLen = hs.length;

    var count = hsLen < segs.length - 1 ? hsLen : segs.length - 1;
    if (count < 0) count = 0;
    if (segs.length !== hsLen + 1) {
      warn.push('trunk.segments(' + segs.length + ') 与 handoffs(' + hsLen +
        ') 数量不匹配：只对能对上的 ' + count + ' 个换手出参数，其余跳过');
    }

    var threads = tree.threads || [];
    var events = tree.events || [];
    var trunkEvents = trunk.events || [];
    var tLen = num(trunk.len, trunkEvents.length);

    var maxOrder = 0;
    for (var k = 0; k < events.length; k++) {
      var o = events[k] ? events[k].order : 0;
      if (typeof o === 'number' && o > maxOrder) maxOrder = o;
    }

    var forks = [];
    var bornCount = 0;

    for (var i = 0; i < count; i++) {
      var h = hs[i] || {};
      var at = num(h.at, -1);
      var tPromote = clamp(num(h.t, 0.5), 0.02, 0.995);
      var toTh = findThread(threads, h.to);
      var fromTh = findThread(threads, h.from);

      var preEvents = pickSide(toTh ? toTh.events : null, at, false);
      var stubEvents = pickSide(fromTh ? fromTh.events : null, at, true);
      var born = preEvents.length > 0;

      var minPos = Infinity;
      if (born) {
        for (var p = 0; p < preEvents.length; p++) {
          var ev = preEvents[p];
          var pos;
          var idx = trunkEvents.indexOf(ev);
          if (idx >= 0) {
            pos = idx / (tLen > 1 ? tLen - 1 : 1);
          } else {
            var evObj = events[ev];
            if (!evObj) continue;
            pos = num(evObj.order, 0) / (maxOrder > 0 ? maxOrder : 1);
          }
          if (pos < minPos) minPos = pos;
        }
      }
      var preSpan = (born && minPos !== Infinity)
        ? clamp(tPromote - minPos, 0.04, 0.34)
        : 0.055;
      if (born) bornCount++;

      var az = ((i + 1) * GOLD) % TAU;
      var segNext = segs[i + 1];
      var segPrev = segs[i];

      forks.push({
        i: i,
        at: at,
        fromId: (typeof h.from === 'string') ? h.from : '',
        toId: (typeof h.to === 'string') ? h.to : '',
        kind: (typeof h.kind === 'string') ? h.kind : '',
        tPromote: tPromote,
        tFork: clamp(tPromote - preSpan, 0.015, tPromote - 0.015),
        born: born,
        preEvents: preEvents,
        preSpan: preSpan,
        tStub0: tPromote,
        tStub1: tPromote + clamp(0.03 + stubEvents.length * 0.012, 0.035, 0.13),
        stubEvents: stubEvents,
        az: az,
        azStub: (az + Math.PI) % TAU,
        lead: (toTh && typeof toTh.lead === 'string') ? toTh.lead : '',
        prevLead: (fromTh && typeof fromTh.lead === 'string') ? fromTh.lead : '',
        shared: (Array.isArray(h.shared) && h.shared.length) ? h.shared.slice(0, 6) : [],
        reason: (typeof h.reason === 'string') ? h.reason : '',
        color: segColor(segNext),
        colorPrev: segColor(segPrev)
      });
    }

    var st = {
      forks: forks.length,
      born: bornCount,
      promoted: forks.length,
      ms: Date.now() - started,
      fp: fp,
      ok: true
    };
    var res = { ok: true, reason: '', fp: fp, forks: forks, warn: warn, stats: st };
    if (fp) cache[fp] = res;
    last = res;
    return res;
  }

  function get() {
    return last;
  }

  function stats() {
    if (!last) return { forks: 0, born: 0, promoted: 0, ms: 0, fp: '', ok: false };
    var s = last.stats;
    return { forks: s.forks, born: s.born, promoted: s.promoted, ms: s.ms, fp: s.fp, ok: s.ok };
  }

  window.CLPromote = { compute: compute, get: get, stats: stats };
})();
