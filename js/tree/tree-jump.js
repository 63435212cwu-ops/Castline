/**
 * @role component
 * @owns js/tree-jump.js
 * @budget 单次调用 O(章数 x 域长)，纯逻辑无时钟；不挂帧循环，每帧新增 0
 * @contract v44
 *
 * CLTreeJump —— 章节梭纯逻辑核。只把「上一章 / 下一章 / 第 ci 章」算成目标 evIdx，
 * 唯一写入经 CLTreeEvents.pick。无内部选中态、无副作用、无依赖时全静默 no-op。
 */
(function () {
  'use strict';

  var NAME = 'tree-jump';
  var ONE_BASED = 1;
  var DEP_METHODS = ['domain', 'chapters', 'get', 'pick', 'firstOfChapter'];

  function dep() {
    var e = window.CLTreeEvents;
    if (!e) return null;
    for (var i = 0; i < DEP_METHODS.length; i++) {
      if (typeof e[DEP_METHODS[i]] !== 'function') return null;
    }
    return e;
  }

  function contains(arr, v) {
    for (var i = 0; i < arr.length; i++) if (arr[i] === v) return true;
    return false;
  }

  function positionOf(arr, v) {
    for (var i = 0; i < arr.length; i++) if (arr[i] === v) return i;
    return -1;
  }

  function readDomain(e) {
    try {
      var d = e.domain();
      return (d && typeof d.length === 'number') ? d : [];
    } catch (err) { return []; }
  }

  function readChapters(e) {
    try {
      var c = e.chapters();
      return (c && typeof c.length === 'number') ? c : [];
    } catch (err) { return []; }
  }

  function current(e) {
    if (!e) return -1;
    try {
      var g = e.get();
      if (g && typeof g.evIdx === 'number' && isFinite(g.evIdx)) return g.evIdx;
    } catch (err) {}
    return -1;
  }

  function firstOf(e, ci) {
    try {
      var f = e.firstOfChapter(ci);
      return (typeof f === 'number' && isFinite(f) && f >= 0) ? f : -1;
    } catch (err) { return -1; }
  }

  function pick(e, evIdx) {
    try { e.pick(evIdx); return true; } catch (err) { return false; }
  }

  function chapterOf(evIdx) {
    var e = dep();
    if (!e) return -1;
    if (!contains(readDomain(e), evIdx)) return -1;
    var chs = readChapters(e);
    for (var i = chs.length - 1; i >= 0; i--) {
      var f = firstOf(e, chs[i].idx);
      if (f >= 0 && evIdx >= f) return chs[i].idx;
    }
    return -1;
  }

  function next() {
    var e = dep();
    var cur = current(e);
    if (!e) return cur;
    var chs = readChapters(e);
    if (!chs.length) return cur;
    if (cur < 0) {
      for (var i = 0; i < chs.length; i++) {
        var f0 = firstOf(e, chs[i].idx);
        if (f0 >= 0) return pick(e, f0) ? f0 : -1;
      }
      return cur;
    }
    var ci = chapterOf(cur);
    if (ci < 0) return cur;
    for (var k = 0; k < chs.length; k++) {
      if (chs[k].idx > ci) {
        var f = firstOf(e, chs[k].idx);
        if (f >= 0) return pick(e, f) ? f : -1;
      }
    }
    return cur;
  }

  function prev() {
    var e = dep();
    var cur = current(e);
    if (!e) return cur;
    var chs = readChapters(e);
    if (!chs.length) return cur;
    if (cur < 0) {
      for (var i = chs.length - 1; i >= 0; i--) {
        var f0 = firstOf(e, chs[i].idx);
        if (f0 >= 0) return pick(e, f0) ? f0 : -1;
      }
      return cur;
    }
    var ci = chapterOf(cur);
    if (ci < 0) return cur;
    for (var k = chs.length - 1; k >= 0; k--) {
      if (chs[k].idx < ci) {
        var f = firstOf(e, chs[k].idx);
        if (f >= 0) return pick(e, f) ? f : -1;
      }
    }
    return cur;
  }

  function go(ci) {
    if (ci == null) return -1;
    var v = Math.floor(+ci);
    if (!isFinite(v)) return -1;
    var e = dep();
    if (!e) return -1;
    var f = firstOf(e, v);
    if (f < 0) return -1;
    return pick(e, f) ? f : -1;
  }

  function label() {
    var e = dep();
    if (!e) return null;
    var cur = current(e);
    if (cur < 0) return null;
    var chs = readChapters(e);
    if (!chs.length) return null;
    var ci = chapterOf(cur);
    if (ci < 0) return null;
    var C = null;
    for (var i = 0; i < chs.length; i++) {
      if (chs[i].idx === ci) { C = chs[i]; break; }
    }
    if (!C) return null;
    var dom = readDomain(e);
    var f = firstOf(e, ci);
    var pos = positionOf(dom, cur);
    var fpos = positionOf(dom, f);
    var idx = (pos >= 0 && fpos >= 0 && pos >= fpos) ? (pos - fpos + ONE_BASED) : ONE_BASED;
    return {
      ci: ci,
      name: String(C.name || ''),
      n: Math.floor(C.n || 0) || 0,
      idx: idx,
      total: chs.length
    };
  }

  function stats() {
    var e = dep();
    var cur = current(e);
    return {
      ready: !!e,
      has: cur >= 0,
      ci: cur >= 0 ? chapterOf(cur) : -1,
      evIdx: cur,
      chapters: readChapters(e).length
    };
  }

  window.CLTreeJump = {
    name: NAME,
    chapterOf: chapterOf,
    next: next,
    prev: prev,
    go: go,
    label: label,
    stats: stats
  };
})();
