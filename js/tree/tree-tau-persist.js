/* @role component · @owns js/tree-tau-persist.js · @budget 0 dom_nodes, 1 timer, <4KB · @contract v41 */
(function () {
  'use strict';

  var NAME = 'tree-tau-persist';
  var KEY = 'castline.tau';
  var POLL_MS = 100;
  var POLL_MAX = 15000;

  var S = {
    ready: false,
    applied: false,
    source: null,
    value: null,
    storage: true,
    hooked: false
  };

  function finiteInRange(v) {
    return (typeof v === 'number' && isFinite(v) && v >= 0 && v <= 5) ? v : null;
  }

  function probeStorage() {
    try {
      var k = KEY + '.probe';
      localStorage.setItem(k, '1');
      localStorage.removeItem(k);
      S.storage = true;
    } catch (e) {
      S.storage = false;
    }
  }

  function load() {
    if (!S.storage) return null;
    try {
      var raw = localStorage.getItem(KEY);
      if (raw === null || raw === '') return null;
      return finiteInRange(parseFloat(raw));
    } catch (e) {
      S.storage = false;
      return null;
    }
  }

  function save(v) {
    if (!S.storage) return false;
    try {
      localStorage.setItem(KEY, String(v));
      return true;
    } catch (e) {
      S.storage = false;
      return false;
    }
  }

  function fromURL() {
    try {
      var raw = new URLSearchParams(location.search).get('tau');
      if (raw === null) return null;
      return finiteInRange(parseFloat(raw));
    } catch (e) {
      return null;
    }
  }

  function applyInitial(sway) {
    var v = fromURL();
    var source = 'url';
    if (v === null) {
      v = load();
      source = 'storage';
    }
    if (v === null) return;
    S.applied = true;
    S.source = source;
    var ret = sway.setWave(v);
    S.value = (typeof ret === 'number' && isFinite(ret)) ? ret : v;
  }

  function wrapSetWave(sway) {
    if (S.hooked) return;
    var orig = sway.setWave;
    if (typeof orig !== 'function') return;
    if (orig.__clTauWrapped) { S.hooked = true; return; }
    var wrapped = function (tau) {
      var ret = orig.apply(this, arguments);
      var out = (typeof ret === 'number' && isFinite(ret)) ? ret : tau;
      S.value = out;
      save(out);
      return ret;
    };
    wrapped.__clTauWrapped = true;
    sway.setWave = wrapped;
    S.hooked = true;
  }

  function hook(sway) {
    S.ready = true;
    applyInitial(sway);
    wrapSetWave(sway);
  }

  function poll() {
    var waited = 0;
    var iv = setInterval(function () {
      var sway = window.CLTreeSway;
      if (sway && typeof sway.setWave === 'function') {
        clearInterval(iv);
        hook(sway);
        return;
      }
      waited += POLL_MS;
      if (waited >= POLL_MAX) clearInterval(iv);
    }, POLL_MS);
  }

  function stats() {
    return {
      ready: S.ready,
      applied: S.applied,
      source: S.source,
      value: S.value,
      storage: S.storage
    };
  }

  window.CLTauPersist = {
    name: NAME,
    KEY: KEY,
    load: load,
    save: save,
    fromURL: fromURL,
    stats: stats
  };

  probeStorage();
  poll();
})();
