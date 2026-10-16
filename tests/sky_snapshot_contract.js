(function () {
  'use strict';
  var api = require('../js/sky/sky-snapshot.js');
  var count = 0;
  function ok(value, label) {
    if (!value) throw new Error('FAIL ' + label);
    count++;
  }
  function leaks(text, label) {
    ok(typeof text === 'string' && text.length > 0, label + ' has user-facing copy');
    ok(!/\.js:\d/.test(text), label + ' copy never leaks a JS frame');
    ok(!/\/Users\//.test(text) && !/[A-Za-z]:\\/.test(text), label + ' copy never leaks an absolute path');
    ok(!/\n\s*at\s/.test(text), label + ' copy never leaks a stack trace');
  }

  var MAGIC = api.PNG_MAGIC;
  ok(MAGIC.length === 8 && MAGIC[0] === 0x89 && MAGIC[1] === 0x50, 'PNG magic bytes constant');
  function pngBytes(body) {
    var b = MAGIC.slice();
    (body || [0x49, 0x48, 0x44, 0x52]).forEach(function (x) { b.push(x); });
    return new Uint8Array(b);
  }
  function fakeCanvas(w, h, opts) {
    opts = opts || {};
    var seq = [];
    var c = {
      width: w, height: h,
      seq: seq,
      render: opts.render === false ? undefined : function () { seq.push('render'); if (opts.renderThrows) throw new Error('boom'); }
    };
    if (opts.encoder !== 'none') {
      if (opts.blob !== undefined || opts.blobThrows) {
        c.toBlob = function (cb, mime) {
          seq.push('read');
          if (opts.blobThrows) throw new Error('toBlob boom');
          ok(mime === 'image/png', 'encoder asked for image/png, not ' + mime);
          var blob = opts.blob;
          if (blob) blob.arrayBuffer = function () { return Promise.resolve(opts.bytes.buffer.slice(opts.bytes.byteOffset, opts.bytes.byteOffset + opts.bytes.byteLength)); };
          cb(blob);
        };
      } else {
        var bytes = opts.bytes || pngBytes();
        c.toDataURL = function () {
          seq.push('read');
          if (opts.urlThrows) throw new Error('toDataURL boom');
          return opts.url === undefined ? 'data:image/png;base64,' + Buffer.from(bytes).toString('base64') : opts.url;
        };
      }
    }
    return c;
  }
  function run(adapterOrCanvas) {
    var adapter = adapterOrCanvas && adapterOrCanvas.canvas !== undefined ? adapterOrCanvas
      : adapterOrCanvas ? { canvas: adapterOrCanvas, render: adapterOrCanvas.render } : adapterOrCanvas;
    return new Promise(function (resolve) { api.captureFrame(adapter, resolve); });
  }

  (async function main() {
    var c1 = fakeCanvas(3840, 2160, { bytes: pngBytes(), blob: { type: 'image/png' } });
    var r1 = await run(c1);
    ok(r1.ok === true, 'capture succeeds on boost-tier 4K buffer');
    ok(r1.width === 3840 && r1.height === 2160, 'export size equals drawingBuffer size (no upscale, no crop)');
    ok(c1.seq.join() === 'render,read', 'render precedes buffer read in the same task: ' + c1.seq.join());
    ok(r1.bytes > 8, 'byte length reported');

    var c1b = fakeCanvas(1440, 900, { bytes: pngBytes(), blob: { type: 'image/png' } });
    var r1b = await run(c1b);
    ok(r1b.ok && r1b.width === 1440 && r1b.height === 900, 'degrade-tier smaller buffer exported at its own honest size');

    var bad = new Uint8Array([0x00, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2]);
    var r2 = await run(fakeCanvas(100, 100, { bytes: bad, blob: { type: 'image/png' } }));
    ok(!r2.ok && r2.kind === 'encode-corrupt', 'forged bytes rejected as encode-corrupt');
    var r2b = await run(fakeCanvas(100, 100, { bytes: new Uint8Array(3), blob: { type: 'image/png' } }));
    ok(!r2b.ok && r2b.kind === 'encode', 'empty bytes rejected as encode failure');

    var r3 = await run(fakeCanvas(512, 512, {}));
    ok(r3.ok && r3.width === 512 && r3.height === 512 && r3.dataUrl && r3.dataUrl.indexOf('data:image/png') === 0, 'toDataURL fallback captures png');
    ok((await run(fakeCanvas(512, 512, { url: 'data:image/heic;base64,AAAA' }))).kind === 'encode', 'non-png dataURL rejected (heic etc. never passes silently)');
    ok((await run(fakeCanvas(512, 512, { urlThrows: true }))).kind === 'encode', 'toDataURL throw surfaces as encode');

    ok((await run(null)).kind === 'no-scene', 'missing adapter rejected as no-scene');
    ok((await run({ canvas: null })).kind === 'no-scene', 'missing canvas rejected as no-scene');
    ok((await run(fakeCanvas(0, 0, { bytes: pngBytes(), blob: {} }))).kind === 'no-webgl', 'zero-size drawing buffer rejected as no-webgl (context lost / no budget)');
    ok((await run(fakeCanvas(100, 100, { renderThrows: true, bytes: pngBytes(), blob: {} }))).kind === 'render', 'render throw surfaces as render failure');
    ok((await run(fakeCanvas(100, 100, { blob: null }))).kind === 'encode', 'toBlob null surfaces as encode failure');
    ok((await run(fakeCanvas(100, 100, { blobThrows: true }))).kind === 'encode', 'toBlob throw surfaces as encode failure');
    ok((await run(fakeCanvas(100, 100, { encoder: 'none' }))).kind === 'encode', 'canvas without a png encoder surfaces as encode failure');

    ['no-scene', 'no-webgl', 'render', 'encode', 'encode-corrupt', 'anything-else'].forEach(function (k, i) {
      leaks(api.why(k), 'why(' + k + ') #' + i);
    });

    var name = api.fileName('cache/f0b45e85aac6c95e584075a2', new Date(2026, 9, 7, 15, 4, 5));
    ok(name === 'starmap-cache-f0b45e85aac6c95e584075a2-20261007-150405.png', 'filename embeds work key plus timestamp: got ' + name);
    ok(api.fileName('三国 演义/卷:一', new Date(2026, 9, 7, 1, 2, 3)).indexOf('starmap-') === 0 && !/[\\/:*?"<>|\s]/.test(api.fileName('三国 演义/卷:一', new Date(2026, 9, 7, 1, 2, 3)).slice(8)), 'filename slug strips unsafe characters');
    ok(api.fileName('', new Date(2026, 9, 7)).indexOf('starmap-work-') === 0, 'empty work key falls back to work');
    ok(/^starmap-.+-\d{8}-\d{6}\.png$/.test(api.fileName('x', new Date(2030, 0, 2, 3, 4, 5))), 'filename matches starmap-<slug>-YYYYMMDD-HHMMSS.png');

    console.log('sky_snapshot_contract: OK (' + count + ' assertions)');
  })().catch(function (e) { console.error(e && e.message || e); process.exit(1); });
})();
