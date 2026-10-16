(function (root) {
  'use strict';
  var VERSION = 'castline/sky-snapshot/1';
  var PNG_MAGIC = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

  function text(v) { return v == null ? '' : String(v); }
  function slug(s) { return text(s).replace(/[\\/:*?"<>|\s]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'work'; }
  function pad(v) { return (v < 10 ? '0' : '') + v; }

  function fileName(workKey, d) {
    d = d instanceof Date ? d : new Date();
    return 'starmap-' + slug(workKey) + '-' + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '-' + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds()) + '.png';
  }

  function why(kind) {
    switch (kind) {
      case 'no-scene': return '还没有可导出的星盘画面：先打开一部作品，再导出快照。';
      case 'no-webgl': return '这张星盘没有可用的图形缓冲（WebGL 未就绪或画布为空），画面取不出来。可以刷新后再试一次。';
      case 'render': return '导出前强制重绘这一步中断了：多半发生在画质档刚切换的瞬间，等半秒再点一次；仍失败就刷新页面。';
      case 'encode': return '图片编码没有产出数据：超高分辨率档位（如 8K）快照过大时可能出现。等画质落回常规档，或把窗口调小一点再导出。';
      case 'encode-corrupt': return '导出到手的字节不是一幅有效的 PNG 图像，已丢弃、没有落盘。这不该发生；重导一次，仍然如此请反馈。';
      default: return '快照导出失败，原因不归入任何已知类别。可以重试一次。';
    }
  }
  function imgFail(cb, kind, detail) {
    var out = { ok: false, kind: kind, message: why(kind) };
    if (detail != null) out.detail = text(detail).slice(0, 200);
    cb(out);
    return out;
  }

  function dataUrlBytes(url) {
    var b64 = url.slice(url.indexOf(',') + 1);
    if (typeof atob === 'function') {
      try {
        var bin = atob(b64), u = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
        return u;
      } catch (e) { return null; }
    }
    if (typeof Buffer !== 'undefined') { try { return Buffer.from(b64, 'base64'); } catch (e2) { return null; } }
    return null;
  }
  function readBytes(blob, cb) {
    if (blob && typeof blob.arrayBuffer === 'function') {
      Promise.resolve(blob.arrayBuffer()).then(function (ab) { cb(new Uint8Array(ab)); }, function (e) { cb(null, e && e.message); });
      return;
    }
    if (root.FileReader) {
      var fr = new FileReader();
      fr.onload = function () { cb(new Uint8Array(fr.result)); };
      fr.onerror = function () { cb(null, 'FileReader error'); };
      fr.readAsArrayBuffer(blob);
      return;
    }
    cb(null, 'no blob byte reader');
  }

  function captureFrame(adapter, cb) {
    adapter = adapter || {}; cb = cb || function () {};
    var canvas = adapter.canvas;
    if (!canvas || typeof canvas !== 'object') return imgFail(cb, 'no-scene');
    var w = canvas.width | 0, h = canvas.height | 0;
    if (!w || !h) return imgFail(cb, 'no-webgl', 'empty drawing buffer ' + canvas.width + 'x' + canvas.height);
    try { if (adapter.render) adapter.render(); } catch (e) { return imgFail(cb, 'render', e && e.message); }
    function deliver(bytes, blob, url) {
      if (!bytes || bytes.length < PNG_MAGIC.length) return imgFail(cb, 'encode', 'empty png bytes');
      for (var i = 0; i < PNG_MAGIC.length; i++) if (bytes[i] !== PNG_MAGIC[i]) return imgFail(cb, 'encode-corrupt', 'png magic mismatch at byte ' + i);
      cb({ ok: true, width: w, height: h, bytes: bytes.length, blob: blob || null, dataUrl: url || null });
    }
    if (typeof canvas.toBlob === 'function') {
      var settled = false;
      try {
        canvas.toBlob(function (blob) {
          if (settled) return; settled = true;
          if (!blob) return imgFail(cb, 'encode', 'toBlob returned null');
          readBytes(blob, function (bytes, err) { if (bytes) return deliver(bytes, blob, null); imgFail(cb, 'encode', err); });
        }, 'image/png');
      } catch (e) { if (!settled) { settled = true; imgFail(cb, 'encode', e && e.message); } }
      return;
    }
    if (typeof canvas.toDataURL === 'function') {
      var url;
      try { url = canvas.toDataURL('image/png'); } catch (e2) { return imgFail(cb, 'encode', e2 && e2.message); }
      if (!url || url.indexOf('data:image/png') !== 0) return imgFail(cb, 'encode', 'bad png dataURL');
      var bytes = dataUrlBytes(url);
      if (!bytes) return imgFail(cb, 'encode', 'png dataURL decode failed');
      deliver(bytes, null, url);
      return;
    }
    imgFail(cb, 'encode', 'canvas has no png encoder');
  }

  var g = typeof window !== 'undefined' ? window : null;
  function app() { return g && g.CLApp || null; }
  function scene() { var A = app(); return A && A.scene ? A.scene() : null; }
  function toast(t, ms) { var A = app(); if (A && A.toast) A.toast(t, ms); }
  function workKey() {
    var A = app(), key = A && A.key ? A.key() : null;
    if (key) return key;
    var graph = A && A.graph ? A.graph() : null;
    return graph && (graph.title || (graph.meta && graph.meta.title)) || 'work';
  }
  function adapter() {
    var S = scene();
    if (!S) return null;
    var canvas = S.renderer && S.renderer.domElement;
    if (!canvas) return null;
    if (typeof S.step === 'function') return { canvas: canvas, render: function () { S.step(1); } };
    if (typeof S.snapshot === 'function') return { canvas: canvas, render: null, legacy: S };
    return null;
  }
  function ready() {
    var ad = adapter();
    return !!(ad && ad.canvas && ad.canvas.width > 0 && ad.canvas.height > 0);
  }

  function download(name, res) {
    if (!g || !g.document) return null;
    var doc = g.document, a = doc.createElement('a'), url = null;
    if (res.blob && g.URL && typeof g.URL.createObjectURL === 'function') {
      url = g.URL.createObjectURL(res.blob);
      a.href = url;
      setTimeout(function () { g.URL.revokeObjectURL(url); if (a.parentNode) a.parentNode.removeChild(a); }, 0);
    } else if (res.dataUrl) {
      a.href = res.dataUrl;
      setTimeout(function () { if (a.parentNode) a.parentNode.removeChild(a); }, 0);
    } else return null;
    a.download = name; a.rel = 'noopener';
    (doc.body || doc.documentElement).appendChild(a);
    a.click();
    return { name: name };
  }

  var busy = false;
  function deliverFail(res, done) {
    toast(res.message || why(res.kind), 5600);
    if (g.console && console.warn) console.warn('[CLSkySnapshot]', res.kind, res.detail || '');
    busy = false;
    done(res);
  }
  function exportNow(done) {
    done = done || function () {};
    if (busy) { toast('上一张快照还在编码，稍候再导出', 2400); done({ ok: false, kind: 'busy', message: why('encode') }); return; }
    var ad = adapter(), name = fileName(workKey(), new Date());
    if (!ad) { deliverFail({ ok: false, kind: 'no-scene', message: why('no-scene') }, done); return; }
    busy = true;
    toast('正在导出星盘快照…', 1500);
    if (ad.legacy) {
      ad.legacy.snapshot(function (url) {
        if (!url) return deliverFail({ ok: false, kind: 'encode', detail: 'frame snapshot returned null', message: why('encode') }, done);
        var bytes = dataUrlBytes(url);
        if (!bytes) return deliverFail({ ok: false, kind: 'encode', detail: 'png dataURL decode failed', message: why('encode') }, done);
        for (var i = 0; i < PNG_MAGIC.length; i++) if (bytes[i] !== PNG_MAGIC[i]) return deliverFail({ ok: false, kind: 'encode-corrupt', detail: 'png magic mismatch', message: why('encode-corrupt') }, done);
        var res = { ok: true, width: ad.canvas.width | 0, height: ad.canvas.height | 0, bytes: bytes.length, blob: null, dataUrl: url, name: name };
        download(name, res);
        toast('星盘快照已导出 · ' + res.width + '×' + res.height + ' · ' + name, 4600);
        busy = false;
        done(res);
      });
      return;
    }
    captureFrame(ad, function (res) {
      if (!res.ok) return deliverFail(res, done);
      res.name = name;
      download(name, res);
      toast('星盘快照已导出 · ' + res.width + '×' + res.height + ' · ' + name, 4600);
      busy = false;
      done(res);
    });
  }

  var api = { version: VERSION, PNG_MAGIC: PNG_MAGIC.slice(), fileName: fileName, why: why,
    captureFrame: captureFrame, ready: ready, exportNow: exportNow, _workKey: workKey };
  if (g) g.CLSkySnapshot = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this);
