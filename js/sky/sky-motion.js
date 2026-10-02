/* @role component
 * @owns js/sky/sky-motion.js
 * @budget n/a（无 GPU / 绘制开销；约 400 条活动 tween 时每帧 ≈ 0.05ms）
 * @contract deep-sky/1
 *
 * 光层编排引擎。无 DOM、无 THREE；唯一时间来源是宿主每帧调用 tick(dt)。
 * 禁止 rAF / setTimeout / setInterval。
 * 数组 tween 的 onUpdate 收到的是该条 tween 自己的复用缓冲，需要留存请自行拷贝。
 */
(function (g) {
  'use strict';

  var MAX_DT = 0.1;

  var items = [];
  var nextId = 1;
  var ticking = false;
  var warned = false;
  var st = { created: 0, finished: 0, cancelled: 0 };

  function num(v) { return typeof v === 'number' && isFinite(v) ? v : 0; }
  function len(a) { return (a && a.length) ? a.length : 0; }

  function easeOut(t) { var u = 1 - t; return 1 - u * u * u * u; }

  function easeOf(e) {
    if (typeof e === 'function') return e;
    var T = g.CLSkyTokens;
    return (T && T.EASE && typeof T.EASE.out === 'function') ? T.EASE.out : easeOut;
  }

  function reduced() {
    var T = g.CLSkyTokens;
    return !!(T && T.reduced && T.reduced());
  }

  function guard(tag, id, fn) {
    if (typeof fn !== 'function') return;
    try {
      fn();
    } catch (e) {
      if (!warned) {
        warned = true;
        if (g.console && g.console.warn) g.console.warn('[sky-motion] ' + (tag || 'step') + '#' + id + ' callback failed', e);
      }
    }
  }

  function apply(h, k) {
    var o = h.o, f = o.from, t = o.to, i, n = h.n;
    if (typeof o.onUpdate !== 'function') return;
    if (n) {
      var b = h.buf;
      for (i = 0; i < n; i++) b[i] = num(f[i]) + (num(t[i]) - num(f[i])) * k;
      o.onUpdate(b, k);
    } else {
      var a = num(f);
      o.onUpdate(a + (num(t) - a) * k, k);
    }
  }

  function compact() {
    var w = 0;
    for (var i = 0; i < items.length; i++) {
      if (!items[i].dead && !items[i].done) items[w++] = items[i];
    }
    items.length = w;
  }

  function detach(h) {
    if (!h.queued) return;
    h.queued = false;
    if (!ticking) {
      var i = items.indexOf(h);
      if (i >= 0) items.splice(i, 1);
    }
  }

  function finish(h) {
    if (h.done || h.dead) return;
    h.done = true;
    h.dead = true;
    apply(h, 1);
    guard(h.tag, h.id, h.o.onDone);
    st.finished++;
    detach(h);
  }

  function tween(o) {
    o = o || {};
    var h = {
      id: nextId++, kind: 'tween', o: o,
      tag: o.tag || null, done: false, dead: false, queued: false, armed: false,
      n: 0, buf: null, t: 0, wait: num(o.delay), dur: num(o.dur), ease: easeOf(o.ease)
    };
    h.cancel = function () { return cancel(h); };
    if (len(o.from) || len(o.to)) {
      h.n = Math.max(len(o.from), len(o.to));
      h.buf = new Array(h.n);
    }
    st.created++;
    if (reduced() || o.instant) { finish(h); return h; }
    h.queued = true;
    items.push(h);
    return h;
  }

  function step(h, d) {
    h.t += d;
    if (h.kind === 'seq') {
      var s = h.steps, e = h.t;
      while (h.k < s.length && num(s[h.k].at) <= e) {
        var b = s[h.k++];
        guard(h.tag, h.id, b && b.fn);
      }
      if (h.k >= s.length) {
        h.done = true; h.dead = true; st.finished++;
        guard(h.tag, h.id, h.onDone);
        detach(h);
      }
      return;
    }
    if (h.t < h.wait) return;
    if (h.dur <= 0) { finish(h); return; }
    var k = (h.t - h.wait) / h.dur;
    if (k >= 1) { finish(h); return; }
    var ek;
    try { ek = h.ease(k); } catch (err) { ek = k; }
    apply(h, typeof ek === 'number' && isFinite(ek) ? ek : k);
  }

  function tick(dt) {
    if (ticking) return;
    var d = num(dt);
    if (d > MAX_DT) d = MAX_DT;
    ticking = true;
    var i, h;
    for (i = 0; i < items.length; i++) items[i].armed = true;
    for (i = 0; i < items.length; i++) {
      h = items[i];
      if (h.dead || h.done || !h.armed) continue;
      step(h, d);
    }
    compact();
    ticking = false;
  }

  function seq(steps, tag) {
    var onDone = null;
    if (typeof tag === 'function') { onDone = tag; tag = null; }
    steps = steps || [];
    var h = {
      id: nextId++, kind: 'seq', steps: steps, onDone: onDone,
      tag: tag || null, done: false, dead: false, queued: false, armed: false, t: 0, k: 0
    };
    h.cancel = function () { return cancel(h); };
    st.created++;
    if (reduced()) {
      for (var i = 0; i < steps.length; i++) guard(h.tag, h.id, steps[i] && steps[i].fn);
      h.done = true;
      st.finished++;
      guard(h.tag, h.id, onDone);
      return h;
    }
    h.queued = true;
    items.push(h);
    return h;
  }

  function stagger(n, span) {
    n = Math.max(0, Math.floor(num(n)));
    var out = [], d = num(span), div = Math.max(1, n - 1);
    for (var i = 0; i < n; i++) out.push(i * d / div);
    return out;
  }

  function cancel(h) {
    if (!h || h.done || h.dead) return false;
    h.dead = true;
    st.cancelled++;
    detach(h);
    return true;
  }

  function cancelAll(tag) {
    var all = (tag === undefined || tag === null), n = 0;
    for (var i = 0; i < items.length; i++) {
      var h = items[i];
      if (h.dead || h.done) continue;
      if (!all && h.tag !== tag) continue;
      h.dead = true; h.queued = false; st.cancelled++; n++;
    }
    if (!ticking) compact();
    return n;
  }

  /* 同标签的补间 / 序列一次跳到终态（揭幕被点击或按键跳过时用） */
  function finishAll(tag) {
    var list = items.slice(), n = 0, i, h, b;
    for (i = 0; i < list.length; i++) {
      h = list[i];
      if (h.dead || h.done || h.tag !== tag) continue;
      if (h.kind === 'seq') {
        while (h.k < h.steps.length) { b = h.steps[h.k++]; guard(h.tag, h.id, b && b.fn); }
        h.done = true; h.dead = true; st.finished++; guard(h.tag, h.id, h.onDone); detach(h);
      } else finish(h);
      n++;
    }
    if (!ticking) compact();
    return n;
  }

  function active() {
    var n = 0;
    for (var i = 0; i < items.length; i++) {
      if (!items[i].dead && !items[i].done) n++;
    }
    return n;
  }

  function stats() {
    return { active: active(), created: st.created, finished: st.finished, cancelled: st.cancelled };
  }

  g.CLSkyMotion = {
    tween: tween,
    seq: seq,
    stagger: stagger,
    tick: tick,
    cancel: cancel,
    cancelAll: cancelAll,
    finishAll: finishAll,
    active: active,
    reduced: reduced,
    stats: stats
  };
})(window);
