/* Castline · tray.js — 材料托盘
 * 用户可分批拖入多个文件夹/文件；托盘累加、去重、分组、可改类型/排除/移除；IndexedDB 持久化；
 * 只有点「开始分析」才会把托盘送去分析。
 */
(function () {
  'use strict';
  var items = [], listeners = [], batchSeq = 0, DB = null, persistSeq = 0, persistQueue = Promise.resolve(), mutationSeq = 0;

  function hashText(s) {
    // 双 32 位滚动摘要，降低大材料内容去重的碰撞概率；全文仍保存在托盘，
    // 摘要只用于识别“完全相同文本”。
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
    // 多次拖入/移除可能在 IndexedDB 建库完成前连续发生；按序写入并跳过
    // 已过期快照，避免旧快照在最后一次操作之后落盘。
    var seq = ++persistSeq, snapshot = items.map(function (it) { var x = {}; Object.keys(it).forEach(function (k) { x[k] = it[k]; }); return x; });
    persistQueue = persistQueue.catch(function () {}).then(function () {
      if (seq !== persistSeq) return;
      return db().then(function (d) {
        if (!d || seq !== persistSeq) return;
        return new Promise(function (resolve) {
          try {
            var st = d.transaction('items', 'readwrite').objectStore('items'); st.put(snapshot, 'tray');
            resolve();
          } catch (e) { resolve(); }
        });
      });
    });
    return persistQueue;
  }
  /** restore：只在托盘还是空的时候采用磁盘快照。
   *  IndexedDB 首次打开要建库，可能要 1s+；这期间用户完全可能已经拖进第一批材料，
   *  直接赋值会把刚拖进来的东西悄悄清空（v16 之前的竞态）。 */
  function restore() {
    var before = mutationSeq;
    return db().then(function (d) {
      if (!d) return items;
      return new Promise(function (res) {
        var tx = d.transaction('items', 'readonly').objectStore('items').get('tray');
        tx.onsuccess = function () {
          var saved = Array.isArray(tx.result) ? tx.result : [];
          if (items.length || mutationSeq !== before) { persist(); return res(items); }   // 用户已经先动手了：以内存为准，反向覆盖磁盘
          items = saved;
          batchSeq = items.reduce(function (m, it) { return Math.max(m, it.batch || 0); }, 0);
          emit(); res(items);
        };
        tx.onerror = function () { res(items); };
      });
    });
  }

  /** add(docs, label) — docs 来自 CLIngest.load；同文本去重（返回新增数与重复数） */
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

  window.CLTray = { add: add, remove: remove, removeBatch: removeBatch, clear: clear, setKind: setKind, toggle: toggle, active: active, totals: totals, payload: payload, groups: groups, items: function () { return items; }, restore: restore, on: on };
})();
