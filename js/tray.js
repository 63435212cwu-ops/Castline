(function () {
  'use strict';
  var items = [], listeners = [], batchSeq = 0, DB = null, persistSeq = 0, persistQueue = Promise.resolve(), mutationSeq = 0, lastPersistError = null;

  function hashText(s) {
    var a = 0x811c9dc5, b = 0x9e3779b9;
    for (var i = 0; i < s.length; i++) { var c = s.charCodeAt(i); a ^= c; a = (a * 0x01000193) >>> 0; b ^= (c + i) & 0xffff; b = (b * 0x85ebca6b) >>> 0; }
    return a.toString(16).padStart(8, '0') + b.toString(16).padStart(8, '0') + ':' + s.length;
  }
  function emit() { listeners.forEach(function (f) { try { f(items); } catch (e) { console.error(e); } }); }

  function db() {
    if (DB) return Promise.resolve(DB);
    return new Promise(function (res) {
      try {
        var req = indexedDB.open('castline-tray', 1);
        req.onupgradeneeded = function () { req.result.createObjectStore('items'); };
        req.onsuccess = function () { DB = req.result; res(DB); };
        req.onerror = function () { res(null); };
      } catch (e) { res(null); }
    });
  }
  function persist() {
    var seq = ++persistSeq, snapshot = items.map(function (it) { var x = {}; Object.keys(it).forEach(function (k) { x[k] = it[k]; }); return x; });
    persistQueue = persistQueue.catch(function () {}).then(function () {
      if (seq !== persistSeq) return;
      return db().then(function (d) {
        if (!d || seq !== persistSeq) return;
        return new Promise(function (resolve) {
          var tx, done = false;
          function finish(err) {
            if (done) return; done = true;
            if (err) { lastPersistError = err; console.warn('CLTray: 持久化失败', err); }
            else lastPersistError = null;
            resolve();
          }
          try {
            tx = d.transaction('items', 'readwrite');
            tx.oncomplete = function () { finish(null); };
            tx.onerror = function () { finish(tx.error || new Error('材料托盘持久化事务失败')); };
            tx.onabort = function () { finish(tx.error || new Error('材料托盘持久化事务中止')); };
            tx.objectStore('items').put(snapshot, 'tray');
          } catch (e) { finish(e); }
        });
      });
    });
    return persistQueue;
  }
  function sanitizeEntry(it, i, usedIds) {
    if (!it || typeof it !== 'object' || typeof it.text !== 'string' || !it.text) return null;
    var id = typeof it.id === 'string' && it.id && !usedIds[it.id] ? it.id : null;
    if (!id) id = 'mr' + Date.now().toString(36) + '-' + i + '-' + Math.floor(Math.random() * 1e4).toString(36);
    usedIds[id] = true;
    var path = typeof it.path === 'string' && it.path ? it.path : (typeof it.name === 'string' && it.name ? it.name : '未命名');
    var batch = typeof it.batch === 'number' && isFinite(it.batch) ? it.batch : 0;
    return {
      id: id,
      hash: typeof it.hash === 'string' && it.hash ? it.hash : hashText(it.text),
      path: path,
      name: typeof it.name === 'string' && it.name ? it.name : path.split('/').pop().replace(/\.[^.]+$/, ''),
      text: it.text,
      bytes: typeof it.bytes === 'number' && isFinite(it.bytes) ? it.bytes : it.text.length,
      ext: typeof it.ext === 'string' && it.ext ? it.ext : (path.split('.').pop() || '').toLowerCase(),
      kind: typeof it.kind === 'string' ? it.kind : null,
      exclude: !!it.exclude,
      batch: batch,
      batchLabel: typeof it.batchLabel === 'string' && it.batchLabel ? it.batchLabel : ('第 ' + batch + ' 批'),
      addedAt: typeof it.addedAt === 'number' && isFinite(it.addedAt) ? it.addedAt : Date.now()
    };
  }
  function restore() {
    var before = mutationSeq;
    return db().then(function (d) {
      if (!d) return items;
      return new Promise(function (res) {
        var tx = d.transaction('items', 'readonly').objectStore('items').get('tray');
        tx.onsuccess = function () {
          if (tx.result != null && !Array.isArray(tx.result)) console.warn('CLTray: 持久化快照不是数组，按空托盘恢复');
          var raw = Array.isArray(tx.result) ? tx.result : [];
          var saved = [], dropped = 0, usedIds = {};
          raw.forEach(function (it, i) { var s = sanitizeEntry(it, i, usedIds); if (s) saved.push(s); else dropped++; });
          if (dropped) console.warn('CLTray: 忽略 ' + dropped + ' 条损坏的持久化条目');
          if (items.length || mutationSeq !== before) { persist(); return res(items); }
          items = saved;
          batchSeq = items.reduce(function (m, it) { return Math.max(m, it.batch || 0); }, 0);
          emit(); res(items);
        };
        tx.onerror = function () { res(items); };
      });
    });
  }

  function add(docs, label) {
    mutationSeq++;
    batchSeq++;
    var seen = {}; items.forEach(function (it) { seen[it.hash] = true; });
    var added = 0, dup = 0, now = Date.now();
    docs.forEach(function (d) {
      var h = hashText(d.text);
      if (seen[h]) { dup++; return; }
      seen[h] = true; added++;
      items.push({ id: 'm' + now.toString(36) + '-' + items.length + '-' + Math.floor(Math.random() * 1e4).toString(36), hash: h, path: d.path, name: d.name, text: d.text, bytes: d.bytes || d.text.length,
        ext: d.ext || (d.path.split('.').pop() || '').toLowerCase(), kind: d.kind || null, exclude: false, batch: batchSeq, batchLabel: label || ('第 ' + batchSeq + ' 批'), addedAt: now });
    });
    persist(); emit();
    return { added: added, dup: dup, batch: batchSeq };
  }
  function remove(id) { mutationSeq++; items = items.filter(function (it) { return it.id !== id; }); persist(); emit(); }
  function removeBatch(b) { mutationSeq++; items = items.filter(function (it) { return it.batch !== b; }); persist(); emit(); }
  function clear() { mutationSeq++; items = []; batchSeq = 0; persist(); emit(); }
  function update(id, patch) { mutationSeq++; items.forEach(function (it) { if (it.id === id) Object.keys(patch).forEach(function (k) { it[k] = patch[k]; }); }); persist(); emit(); }
  function setKind(id, kind) { update(id, { kind: kind }); }
  function toggle(id, on) { update(id, { exclude: !on }); }
  function active() { return items.filter(function (it) { return !it.exclude; }); }
  function totals() {
    var a = active(), chars = a.reduce(function (t, it) { return t + it.text.length; }, 0);
    var batches = {}; items.forEach(function (it) { batches[it.batch] = (batches[it.batch] || 0) + 1; });
    return { files: items.length, active: a.length, chars: chars, batches: Object.keys(batches).length };
  }
  function payload() { return active().map(function (it) { return { path: it.path, name: it.name, text: it.text, kind: it.kind || undefined }; }); }
  function groups() {
    var map = {}, order = [];
    items.forEach(function (it) { if (!map[it.batch]) { map[it.batch] = { batch: it.batch, label: it.batchLabel, items: [] }; order.push(it.batch); } map[it.batch].items.push(it); });
    return order.map(function (b) { return map[b]; });
  }
  function on(fn) { listeners.push(fn); }

  window.CLTray = { add: add, remove: remove, removeBatch: removeBatch, clear: clear, setKind: setKind, toggle: toggle, active: active, totals: totals, payload: payload, groups: groups, items: function () { return items; }, restore: restore, on: on, lastPersistError: function () { return lastPersistError; } };
})();
