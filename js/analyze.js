/* Castline · analyze.js — v17.1
 * 调 /api/analyze，消费 SSE；结果缓存 IndexedDB；支持取消、断流自动重连附着、作业发现。
 *   CLAnalyze.run(docs, {force, refresh, onEvent, control})  → Promise<graph>
 *     force   = 忽略全部缓存重跑；refresh = 忽略图谱缓存、复用已完成的块（补齐 / 续跑）
 *     control（可选对象）会被填上 { job, abort(), cancel() }
 *     取消时 reject 一个 err.cancelled === true 的错误
 *   CLAnalyze.jobs()          → Promise<[{job,key,started,stage,done,n,...}]>
 *   CLAnalyze.cancel(job)     → Promise<{ok}>
 */
(function () {
  'use strict';

  function hashDocs(docs, namespace) {
    // 双 32 位摘要，用作 IndexedDB 键（服务端另有 SHA-1 缓存）。路径、
    // 类型和分隔符都纳入，避免不同材料组合意外命中同一条本地结果。
    var h = 0x811c9dc5, h2 = 0x9e3779b9, ns = String(namespace || '');
    for (var ni = 0; ni < ns.length; ni++) { var nc = ns.charCodeAt(ni); h ^= nc; h = (h * 0x01000193) >>> 0; h2 ^= (nc + ni) & 0xffff; h2 = (h2 * 0x85ebca6b) >>> 0; }
    for (var i = 0; i < docs.length; i++) {
      // 材料类型参与本地缓存键：同一份文本从“正文”改成“设定”后，
      // 模型上下文策略和结果可能不同，不能复用旧图谱。
      var s = JSON.stringify([docs[i].path || '', docs[i].name || '', docs[i].sourceId || docs[i].id || '', docs[i].kind || '', docs[i].text || '']);
      for (var j = 0; j < s.length; j++) { var c = s.charCodeAt(j); h ^= c; h = (h * 0x01000193) >>> 0; h2 ^= (c + j + i) & 0xffff; h2 = (h2 * 0x85ebca6b) >>> 0; }
    }
    return 'nc-' + h.toString(16).padStart(8, '0') + h2.toString(16).padStart(8, '0') + '-' + docs.length;
  }

  var DB = null;
  function db() {
    if (DB) return Promise.resolve(DB);
    return new Promise(function (res) {
      try {
        var req = indexedDB.open('castline', 1);
        req.onupgradeneeded = function () { req.result.createObjectStore('graphs'); };
        req.onsuccess = function () { DB = req.result; res(DB); };
        req.onerror = function () { res(null); };
      } catch (e) { res(null); }
    });
  }
  function cacheGet(key) {
    return db().then(function (d) {
      if (!d) return null;
      return new Promise(function (res) {
        var tx = d.transaction('graphs', 'readonly').objectStore('graphs').get(key);
        tx.onsuccess = function () { res(tx.result || null); };
        tx.onerror = function () { res(null); };
      });
    });
  }
  function cachePut(key, val) {
    return db().then(function (d) {
      if (!d) return;
      try { d.transaction('graphs', 'readwrite').objectStore('graphs').put(val, key); } catch (e) {}
    });
  }

  function jobs() { return fetch('/api/jobs').then(function (r) { return r.json(); }).then(function (d) { return d.jobs || []; }).catch(function () { return []; }); }
  function cancel(job) {
    return fetch('/api/cancel', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ job: job || '' }) })
      .then(function (r) { return r.json(); }).catch(function () { return { ok: false }; });
  }

  function cancelErr(msg) { var e = new Error(msg || '已取消分析'); e.cancelled = true; return e; }

  /** 一次连接：把 SSE 事件喂给 emit；返回 Promise<graph>；断流则 reject 并标记 .stream */
  function connect(payload, emit, ctl, key) {
    var ac = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    ctl.abort = function () { ctl.aborted = true; if (ac) try { ac.abort(); } catch (e) {} };
    return fetch('/api/analyze', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload), signal: ac ? ac.signal : undefined
    }).catch(function (e) {
      if (ctl.aborted) throw cancelErr();
      throw new Error('无法连接本地服务（' + (e && e.message) + '）。请确认 python3 -s serve.py 8000 正在运行。');
    }).then(function (resp) {
      if (!resp.ok) throw new Error('服务返回 ' + resp.status + '。请重启 python3 -s serve.py 8000。');
      if (!resp.body) throw new Error('浏览器不支持流式响应');
      var reader = resp.body.getReader(), dec = new TextDecoder('utf-8'), buf = '';
      return new Promise(function (res, rej) {
        var result = null, ended = false;
        function fin(fn, arg) { if (ended) return; ended = true; fn(arg); }
        function pump() {
          reader.read().then(function (r) {
            if (r.done) {
              if (result) return fin(res, result);
              if (ctl.aborted) return fin(rej, cancelErr());
              var e = new Error('与服务端的连接中断'); e.stream = true; return fin(rej, e);
            }
            buf += dec.decode(r.value, { stream: true });
            var idx;
            while ((idx = buf.indexOf('\n\n')) >= 0) {
              var block = buf.slice(0, idx); buf = buf.slice(idx + 2);
              var ev = 'message', data = '';
              block.split('\n').forEach(function (ln) {
                if (ln.indexOf('event:') === 0) ev = ln.slice(6).trim();
                else if (ln.indexOf('data:') === 0) data += ln.slice(5).trim();
              });
              var obj = null;
              try { obj = data ? JSON.parse(data) : {}; } catch (e2) { obj = { raw: data }; }
              if (ev === 'hello') { ctl.job = obj.job; ctl.cancel = function () { ctl.cancelling = true; return cancel(obj.job); }; }
              if (ev === 'error') { emit(ev, obj); return fin(rej, new Error(obj.message || '分析失败')); }
              if (ev === 'cancelled') { emit(ev, obj); var ce = cancelErr(obj.message); if (obj.salvaged) { ce.salvagedKey = obj.key; ce.salvagedTitle = obj.title; if (obj.graph && (payload.mode !== 'deep' || obj.graph.meta && obj.graph.meta.mode === 'deep')) cachePut(key, obj.graph); } return fin(rej, ce); }
              if (ev === 'done') {
                if (payload.mode === 'deep' && (!obj.graph || !obj.graph.meta || obj.graph.meta.mode !== 'deep')) return fin(rej, new Error('后台未返回深度模式结果，请重启本地服务后再试；本次结果未写入深度缓存。'));
                result = obj.graph; cachePut(key, result);
              }
              emit(ev, obj);
            }
            pump();
          }).catch(function (e) {
            if (ctl.aborted) return fin(rej, cancelErr());
            var e2 = new Error('读取分析流失败：' + (e && e.message)); e2.stream = true; fin(rej, e2);
          });
        }
        pump();
      });
    });
  }

  /** run(docs, {force, onEvent, control}) → Promise<graph> */
  function run(docs, opt) {
    opt = opt || {};
    var analysisMode = opt.mode === 'deep' ? 'deep' : 'summary';
    var modelKey = opt.modelKey || opt.model || '';
    var key = hashDocs(docs, analysisMode === 'deep' ? modelKey + '|deep-v4' : modelKey);
    var emit = opt.onEvent || function () {};
    var ctl = opt.control || {};
    var payload = { docs: docs.map(function (d) { return { path: d.path, name: d.name, sourceId: d.sourceId, id: d.id, text: d.text, kind: d.kind }; }), force: !!opt.force, refresh: !!opt.refresh, mode: analysisMode };
    if (opt.job) payload.job = opt.job;
    var start = (opt.force || opt.refresh || opt.job) ? Promise.resolve(null) : cacheGet(key);
    return start.then(function (hit) {
      if (hit && (analysisMode !== 'deep' || hit.meta && hit.meta.mode === 'deep')) { emit('stage', { stage: 'cache', text: '命中本地缓存' }); emit('done', { graph: hit, cached: true, local: true, key: key }); return hit; }
      return connect(payload, emit, ctl, key).catch(function (e) {
        // 断流：作业仍在服务端跑（块级缓存 + 作业注册），自动重连附着一次，不重复计费
        if (!e.stream || ctl.aborted || ctl.cancelling) throw e;
        emit('reconnect', { message: '连接中断，正在重新附着到服务端作业…' });
        if (ctl.job) payload.job = ctl.job; // 只附着原作业，完成后重放结果；禁止force断流重复计费。
        return new Promise(function (r) { setTimeout(r, 1200); }).then(function () {
          return connect(payload, emit, ctl, key).catch(function (e2) {
            if (e2.stream) throw new Error('与服务端的连接中断且重连失败（服务端可能已重启）。已完成的块已缓存，点「重试 · 续跑」继续。');
            throw e2;
          });
        });
      });
    });
  }

  window.CLAnalyze = { run: run, hashDocs: hashDocs, jobs: jobs, cancel: cancel };
})();
