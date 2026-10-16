(function (root) {
  'use strict';
  var VERSION = 'castline/boot-errors/1';
  var SLOW_MS = 15000;
  var CATEGORY = { http: 'network', net: 'network', slow: 'network', json: 'data', shape: 'data', mount: 'data' };
  var KINDS = Object.keys(CATEGORY).concat(['unknown']);

  function normalizeKind(raw) {
    var kind = raw && typeof raw.kind === 'string' ? raw.kind : '';
    return CATEGORY[kind] ? kind : 'unknown';
  }
  function classify(raw) {
    raw = raw && typeof raw === 'object' ? raw : {};
    var kind = normalizeKind(raw);
    var category = kind === 'unknown' ? 'unknown' : CATEGORY[kind];
    return {
      kind: kind,
      category: category,
      retryable: category === 'network',
      status: typeof raw.status === 'number' && isFinite(raw.status) ? raw.status : 0,
      src: raw.src == null ? '' : String(raw.src)
    };
  }
  function retryable(raw) { return classify(raw).retryable; }

  function why(raw) {
    var c = classify(raw);
    switch (c.kind) {
      case 'http':
        return c.status === 404
          ? '找不到这份图谱文件：它可能已被删除或改名，链接里的地址也可能写错了。文件恢复后点「重试」，或回作品库另选一部。'
          : '服务器没有返回这份图谱（HTTP ' + c.status + '）：本地服务可能出了状况。稍候点「重试」，或回作品库另选一部。';
      case 'net':
        return '读取图谱时连接中断：本地服务可能已停止，或网络出了问题。恢复后点「重试」。';
      case 'slow':
        return '读取这份图谱超过 ' + Math.round(SLOW_MS / 1000) + ' 秒还没有返回：本地服务可能已停止，或这份数据特别大。可以再等，也可以点「重试」。';
      case 'json':
        return '这份图谱文件已损坏或不完整：内容无法按 JSON 读取。这与「没有数据」是两回事——重试不会修好文件本身；请换一份数据，或回作品库另选一部。';
      case 'shape':
        return '这个文件不是图谱数据：里面没有角色列表。重试不会改变它的内容；请确认选对了文件，或回作品库另选一部。';
      case 'mount':
        return '图谱数据已取到，但展开时失败了，重试多半会重复同样的失败。请回作品库另选一部，或换一份数据再开。';
      default:
        return '这张星图没能展开，原因不归入任何已知类别。可以点「重试」碰一次运气，或回作品库另选一部。';
    }
  }

  function detail(raw) {
    raw = raw && typeof raw === 'object' ? raw : {};
    var c = classify(raw);
    var parts = ['类别：' + (c.category === 'network' ? '网络/连接（可重试）' : c.category === 'data' ? '数据错误（重试不改变文件）' : '未知'),
      '内部代码：' + c.kind];
    if (c.status) parts.push('HTTP 状态：' + c.status);
    if (baseName(c.src)) parts.push('地址：' + c.src);
    var msg = raw.message == null ? '' : String(raw.message).trim();
    if (msg) parts.push('原始信息：' + msg);
    return parts.join(' · ');
  }
  function baseName(src) { return typeof src === 'string' && src; }
  function slowInfo(src) { return { kind: 'slow', status: 0, message: '', src: src || '' }; }

  var api = { version: VERSION, SLOW_MS: SLOW_MS, kinds: KINDS.slice(),
    classify: classify, retryable: retryable, why: why, detail: detail, slowInfo: slowInfo };
  root.CLBootErrors = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
