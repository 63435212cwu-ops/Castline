/* Browser-only observation hook. Production methods execute unchanged against real DOM/scene. */
(function () {
  'use strict';
  var nativeSet = window.setTimeout, nativeClear = window.clearTimeout;
  var owner = '', controlled = false, clock = 0, serial = 2000000000, tasks = new Map();
  var state = window.__shellRegression = { ctx: null, unit: null, reveals: 0, warms: 0, entries: [], fired: [], canceled: [] };
  function scope(name, fn, that, args) { var previous = owner; owner = name; try { return fn.apply(that, args || []); } finally { owner = previous; } }
  window.setTimeout = function (fn, ms) {
    var name = owner, args = Array.prototype.slice.call(arguments, 2);
    if (typeof fn !== 'function' || (name !== 'load' && name !== 'leave')) return nativeSet.apply(window, arguments);
    if (controlled) { var id = ++serial; tasks.set(id, { id: id, fn: fn, args: args, name: name, due: clock + Math.max(0, +ms || 0) }); return id; }
    return nativeSet(function () { return scope(name, fn, window, args); }, ms);
  };
  window.clearTimeout = function (id) { if (tasks.has(id)) { state.canceled.push(id); tasks.delete(id); return; } return nativeClear.call(window, id); };
  function wrap(object, key, name, observe) {
    var original = object[key]; if (typeof original !== 'function') return;
    object[key] = function () { if (observe) observe.apply(this, arguments); return scope(name, original, this, arguments); };
  }
  function trap(key, decorate) { var value; Object.defineProperty(window, key, { configurable: true, enumerable: true, get: function () { return value; }, set: function (next) { value = next; decorate(next); } }); }
  trap('CLSkyLoader', function (api) {
    var create = api.create; api.create = function () {
      var loader = create.apply(this, arguments);
      ['show', 'hide', 'title', 'stage', 'log', 'counts', 'glyphs'].forEach(function (k) { wrap(loader, k, 'loader'); });
      wrap(loader, 'done', 'leave'); return loader;
    };
  });
  trap('CLSkyDeep', function (api) { wrap(api, 'reveal', 'deep', function () { state.reveals++; }); });
  trap('CLSkyShellLoad', function (api) {
    var create = api.create; api.create = function (ctx) {
      var unit = create.apply(this, arguments); state.ctx = ctx; state.unit = unit;
      ['onLoading', 'afterGraph', 'liftCurtain'].forEach(function (key) { wrap(unit, key, 'load', function () { state.entries.push(key); }); });
      var scene = ctx.scene(), original = scene && scene.compileWarm;
      if (original && !scene.__regressionWarmWrapped) {
        scene.compileWarm = function () { if (owner === 'load') state.warms++; return original.apply(this, arguments); };
        scene.__regressionWarmWrapped = true;
      }
      return unit;
    };
  });
  function run(task) { tasks.delete(task.id); clock = task.due; state.fired.push({ id: task.id, name: task.name, at: clock }); scope(task.name, task.fn, window, task.args); }
  state.control = {
    begin: function () { if (tasks.size) throw new Error('previous loader callbacks remain'); controlled = true; clock = 0; state.fired = []; state.canceled = []; },
    advance: function (ms) { var end = clock + ms, n = 0; while (true) { var next = Array.from(tasks.values()).filter(function (x) { return x.due <= end; }).sort(function (a, b) { return a.due - b.due || a.id - b.id; })[0]; if (!next) break; if (++n > 100) throw new Error('loader timer loop'); run(next); } clock = end; },
    next: function (name) { var next = Array.from(tasks.values()).filter(function (x) { return x.name === name; }).sort(function (a, b) { return a.due - b.due || a.id - b.id; })[0]; if (!next) throw new Error('no pending ' + name + ' callback'); run(next); },
    fire: function (id) { var task = tasks.get(id); if (!task) throw new Error('required loader timer missing'); run(task); },
    pending: function (name) { return Array.from(tasks.values()).filter(function (x) { return !name || x.name === name; }).map(function (x) { return { id: x.id, name: x.name, due: x.due }; }); },
    end: function () { if (tasks.size) throw new Error('test left pending loader callbacks'); controlled = false; },
    cleanup: function () { tasks.clear(); controlled = false; }
  };
  state.read = function () {
    var ctx = state.ctx, loader = ctx && ctx.loader, root = document.querySelector('.skd-loader');
    return { loader: loader && loader.stats(), hidden: root ? root.hidden : null, cls: root && root.className,
      display: root ? getComputedStyle(root).display : null,
      box: root ? [root.getBoundingClientRect().width, root.getBoundingClientRect().height] : null,
      title: root && root.querySelector('.skd-loader__title') ? root.querySelector('.skd-loader__title').textContent : null,
      graph: window.CLApp && CLApp.graph() ? CLApp.graph().title : null, reveals: state.reveals, warms: state.warms,
      sel: ctx && ctx.selInfo ? ctx.selInfo.id : null, deck: ctx && ctx.deckInfo ? ctx.deckInfo.id : null,
      plot: window.CLSky && CLSky.plot(), focused: window.CLSky && CLSky.disc() ? CLSky.disc().focused() : null };
  };
})()
