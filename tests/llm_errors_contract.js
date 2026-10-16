(function () {
  'use strict';
  var api;
  if (typeof require === 'function') {
    api = require('../js/core/llm-errors.js');
  } else {
    api = Function(read('js/core/llm-errors.js') + '\nreturn (typeof window!=="undefined"?window:globalThis).CLLlmErrors;')();
  }
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

  var network = [
    { status: 500, src: '/api/distill' },
    { status: 502, src: '/api/llm-config' },
    { status: 404, src: '/api/enrich/plan' },
    { kind: 'net', src: '/api/distill' },
    { kind: 'slow', src: '/api/enrich/plan' },
    { rejection: new TypeError('Failed to fetch'), src: '/api/llm-config' }
  ];
  network.forEach(function (raw, i) {
    var c = api.classify(raw);
    ok(c.category === 'network' && c.retryable === true, 'network input #' + i + ' classified retryable (' + c.kind + ')');
    leaks(api.why(raw), 'network #' + i);
    leaks(api.detail(raw), 'network detail #' + i);
  });

  var auth403 = { status: 403, src: '/api/llm-config' };
  var c403 = api.classify(auth403);
  ok(c403.kind === 'auth' && c403.category === 'auth' && c403.retryable === false, '403 is an auth refusal, not presented as plain retryable network');
  ok(api.why(auth403).indexOf('拒绝') >= 0 && api.why(auth403).indexOf('403') >= 0, 'auth copy names the refusal and the status');
  ok(api.classify({ status: 401 }).kind === 'auth', '401 shares the auth bucket');
  leaks(api.why(auth403), 'auth');

  var corrupt = { kind: 'corrupt', status: 200, src: '/api/distill', message: 'Unexpected token <' };
  var cc = api.classify(corrupt);
  ok(cc.category === 'data' && cc.retryable === false, 'corrupt response is data, retry is not presented as a fix');
  ok(api.why(corrupt).indexOf('返回内容不是预期的数据格式') >= 0, 'corrupt copy says the response is not the expected data format');
  ok(api.why(corrupt).indexOf('Unexpected token') < 0, 'corrupt friendly copy never embeds the raw parse error');
  ok(api.detail(corrupt).indexOf('Unexpected token') >= 0, 'corrupt detail keeps the raw diagnostic');
  ok(api.why(corrupt).indexOf('没有数据') < 0, 'corrupt copy never pretends this is "no data"');
  leaks(api.why(corrupt), 'corrupt');

  ok(api.why({ kind: 'slow' }).indexOf('15') >= 0, 'slow copy states the timeout');
  ok(api.classify({ rejection: (function () { var e = new Error('x'); e.name = 'AbortError'; return e; })() }).kind === 'slow', 'AbortError maps to the own slow gate');
  ok(api.why({ status: 404 }).indexOf('旧版本') >= 0, '404 copy names the stale server process, not a missing file');
  ok(api.kindFromStatus(403) === 'auth' && api.kindFromStatus(500) === 'http' && api.kindFromStatus(200) === '', 'status derivation is explicit');
  ok(api.kindFromRejection(new TypeError('fetch failed')) === 'net', 'rejection derivation is explicit');

  [null, undefined, {}, { kind: '??' }, { kind: 'http_x' }, 'net', 7, { status: 'abc' }].forEach(function (raw, i) {
    var c = api.classify(raw);
    ok(c.kind === 'unknown' && c.category === 'unknown' && c.retryable === false, 'unknown input #' + i + ' falls into the honest unknown bucket');
    leaks(api.why(raw), 'unknown ' + i);
  });
  ok(api.kinds.length === 6 && api.kinds.indexOf('corrupt') >= 0 && api.kinds.indexOf('auth') >= 0, 'kind catalogue is explicit');
  ok(api.retryable({ status: 500 }) === true && api.retryable({ kind: 'corrupt' }) === false && api.retryable({ status: 403 }) === false, 'retryable() follows the same categories');
  ok(api.SLOW_MS === 15000, 'slow gate constant is published');

  var line = 'llm_errors_contract OK · ' + count + ' checks';
  if (typeof process !== 'undefined' && process.stdout) process.stdout.write(line + '\n');
  else if (typeof print === 'function') print(line);
})();
