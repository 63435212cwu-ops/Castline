(function (root) {
  'use strict';
  var VERSION = 'castline/sky-fullscreen/1';

  function text(v) { return v == null ? '' : String(v); }
  function why(kind) {
    switch (kind) {
      case 'unsupported': return '此浏览器不支持整页全屏（部分移动端浏览器不支持 Fullscreen API），「全屏」已停用。';
      case 'denied': return '浏览器拒绝了全屏请求：可能是缺少直接的用户手势（请再点一次按钮），或页面嵌在不允许全屏的框架里。';
      case 'error': return '全屏切换中途出错，状态没有改变；可以再点一次。';
      default: return '无法完成全屏切换，原因不归入任何已知类别；可以再点一次。';
    }
  }

  function supported(doc) { var e = doc && doc.documentElement; return !!(e && (typeof e.requestFullscreen === 'function' || typeof e.webkitRequestFullscreen === 'function')); }
  function active(doc) { return !!(doc && (doc.fullscreenElement || doc.webkitFullscreenElement)); }

  function toggle(doc, cb) {
    cb = cb || function () {};
    function fail(kind, detail) {
      var r = { ok: false, kind: kind, message: why(kind) };
      if (detail != null) r.detail = text(detail).slice(0, 200);
      cb(r);
      return r;
    }
    if (!supported(doc)) return fail('unsupported');
    var e = doc.documentElement, was = active(doc), res = { ok: true, action: was ? 'exit' : 'enter' }, p;
    try {
      if (was) p = (typeof doc.exitFullscreen === 'function') ? doc.exitFullscreen() : doc.webkitExitFullscreen();
      else p = (typeof e.requestFullscreen === 'function') ? e.requestFullscreen() : e.webkitRequestFullscreen();
    } catch (err) { return fail('error', err && err.message); }
    if (p && typeof p.then === 'function') {
      p.then(function () { cb(res); }, function (err) { fail('denied', err && err.message); });
      return res;
    }
    cb(res);
    return res;
  }

  function syncButton(btn, doc) {
    if (!btn) return null;
    if (!supported(doc)) {
      btn.disabled = true;
      btn.setAttribute('aria-disabled', 'true');
      btn.removeAttribute('aria-pressed');
      if (btn.classList) btn.classList.remove('on');
      btn.title = why('unsupported');
      return { supported: false };
    }
    var full = active(doc);
    btn.disabled = false;
    btn.setAttribute('aria-disabled', 'false');
    btn.setAttribute('aria-pressed', full ? 'true' : 'false');
    if (btn.classList) btn.classList.toggle('on', full);
    if ('textContent' in btn) btn.textContent = full ? '退出全屏' : '全屏';
    btn.title = full ? '退出全屏（F）' : '全屏（F）';
    return { supported: true, active: full };
  }

  /* 接线：#btnFull 点击 → toggle；真实 fullscreenchange（含 F11 系统级、Esc 原生退出）→ 按钮同步。
   * 返回件如实列出注册过的监听——契约据此断言不存在 keydown（Esc 原生行为不能被拦截）。 */
  function wire(env) {
    env = env || {};
    var doc = env.doc, btn = env.btn, out = { wired: false, unsupported: false, listeners: [] };
    if (!doc || !btn || typeof btn.addEventListener !== 'function' || typeof doc.addEventListener !== 'function') return out;
    var failToast = function (res) { if (!res.ok && env.toast) env.toast(res.message || why(res.kind), 4200); };
    var sync = function () { syncButton(btn, doc); };
    btn.addEventListener('click', function () { toggle(doc, failToast); });
    doc.addEventListener('fullscreenchange', sync);
    doc.addEventListener('webkitfullscreenchange', sync);
    out.listeners = ['click', 'fullscreenchange', 'webkitfullscreenchange'];
    if (!supported(doc)) out.unsupported = true;
    out.wired = true;
    sync();
    return out;
  }

  var g = root && root.document ? root : null;
  if (g) {
    wire({
      doc: g.document,
      btn: g.document.getElementById('btnFull'),
      toast: function (t, ms) { var A = g.CLApp; if (A && A.toast) A.toast(t, ms); }
    });
  }

  var api = { version: VERSION, why: why, supported: supported, active: active, toggle: toggle, syncButton: syncButton, wire: wire };
  if (g) g.CLSkyFullscreen = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : typeof globalThis !== 'undefined' ? globalThis : this);
