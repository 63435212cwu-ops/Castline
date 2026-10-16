(function (root) {
  'use strict';
  var VERSION = 'castline/llm-errors/1';
  var SLOW_MS = 15000;
  var CATEGORY = { auth: 'auth', corrupt: 'data', http: 'network', net: 'network', slow: 'network' };
  var KINDS = Object.keys(CATEGORY).concat(['unknown']);

  function kindFromStatus(status) {
    if (status === 401 || status === 403) return 'auth';
    if (typeof status === 'number' && isFinite(status) && status >= 400) return 'http';
    return '';
  }
  function kindFromRejection(err) {
    var name = err && typeof err.name === 'string' ? err.name : '';
    if (name === 'AbortError') return 'slow';
    if (name === 'TypeError') return 'net';
    var msg = String(err && err.message || '');
    if (/Failed to fetch|NetworkError|Load failed/i.test(msg)) return 'net';
    return '';
  }
  function classify(raw) {
    raw = raw && typeof raw === 'object' ? raw : {};
    var kind = typeof raw.kind === 'string' && CATEGORY[raw.kind] ? raw.kind : '';
    if (!kind) kind = kindFromStatus(raw.status);
    if (!kind && raw.rejection) kind = kindFromRejection(raw.rejection);
    if (!kind) kind = 'unknown';
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
      case 'auth':
        return '本地服务拒绝了这次请求（HTTP ' + c.status + '）：重试多半重复同样的拒绝。请确认是从本机打开的页面；如果刚改动过本地服务或配置，重启之后再来一次。';
      case 'corrupt':
        return '服务返回内容不是预期的数据格式：这次响应已损坏，或后台跑的是与页面不匹配的版本。重试多半拿到同样的内容；请把本地服务重启到最新代码后再试。';
      case 'http':
        return c.status === 404
          ? '本地服务没有提供这个接口（HTTP 404）：后台多半是旧版本的进程。请把本地服务重启到最新代码后重试。'
          : '本地服务处理这次请求失败（HTTP ' + c.status + '）：这通常是暂时故障。稍候重试；反复出现请重启本地服务。';
      case 'net':
        return '没有连上本地服务：它可能已停止或刚重启。确认 python3 -s serve.py 正在运行后重试。';
      case 'slow':
        return '请求超过 ' + Math.round(SLOW_MS / 1000) + ' 秒没有返回：本地服务可能已停止、正忙着处理上一个请求，或挂起了。可以重试；这次操作没有产生任何写入或模型调用。';
      default:
        return '这次调用失败的原因不归入任何已知类别。可以重试碰一次运气，或重启本地服务后再试。';
    }
  }

  function detail(raw) {
    raw = raw && typeof raw === 'object' ? raw : {};
    var c = classify(raw);
    var parts = ['类别：' + (c.category === 'network' ? '网络/服务暂时故障（可重试）' : c.category === 'auth' ? '接入被拒绝（先改变条件再重试）' : c.category === 'data' ? '响应损坏（重试不改变内容）' : '未知'),
      '内部代码：' + c.kind];
    if (c.status) parts.push('HTTP 状态：' + c.status);
    if (c.src) parts.push('接口：' + c.src);
    var msg = raw.message == null ? '' : String(raw.message).trim();
    if (msg) parts.push('原始信息：' + msg);
    return parts.join(' · ');
  }

  var api = { version: VERSION, SLOW_MS: SLOW_MS, kinds: KINDS.slice(),
    classify: classify, retryable: retryable, why: why, detail: detail, kindFromStatus: kindFromStatus, kindFromRejection: kindFromRejection };
  root.CLLlmErrors = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
