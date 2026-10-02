/*!
 * @role deepviews
 * @owns js/sky/sky-deep-views.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 视角栏 DOM 与当前视角同步；点击时读取当前控制器，换书不捕获旧状态。
 * 相机生命周期与帧更新仍由 sky-deep / sky-view 承担，无自有帧循环。
 */
(function (g) {
  'use strict';
  function create(o) {
    var mk = g.CLSkyUtil.mk, viewsEl = null;
  /* ── 视角预设 ─────────────────────────────────────── */
  var GLYPH = {
    top: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.2"/></svg>',
    std: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12" rx="9" ry="6"/><circle cx="12" cy="12" r="2"/></svg>',
    tilt: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="13" rx="9.5" ry="3.6"/><path d="M12 4v5"/><circle cx="12" cy="13" r="1.6"/></svg>',
    tour: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 12a7.5 7.5 0 0 1 13-5.1"/><path d="M19.5 12a7.5 7.5 0 0 1-13 5.1"/><path d="M17.8 3.8v3.4h-3.4M6.2 20.2v-3.4h3.4"/></svg>'
  };
  function buildViews(host) {
    if (viewsEl || !host) return;
    viewsEl = mk('div', 'skd-views', host); viewsEl.setAttribute('role', 'toolbar'); viewsEl.setAttribute('aria-label', '视角');
    [['top', '俯瞰（正视，最清晰）'], ['std', '标准视角'], ['tilt', '斜视（更立体）'], ['tour', '环游（缓慢绕行）']].forEach(function (p) {
      var b = mk('button', 'skd-view', viewsEl); b.type = 'button'; b.setAttribute('data-view', p[0]); b.setAttribute('aria-pressed', 'false'); b.title = p[1];
      b.innerHTML = GLYPH[p[0]] + '<span>' + p[1].split('（')[0] + '</span>';
    });
    viewsEl.addEventListener('click', function (e) {
      var b = e.target.closest && e.target.closest('[data-view]'), view = o.view(); if (!b || !view) return;
      var k = b.getAttribute('data-view');
      if (k === 'tour') view.tour(!view.current().tour); else view.preset(k);
      syncViews();
    });
  }
  function syncViews() {
    var view = o.view();
    if (!viewsEl) return;
    viewsEl.hidden = o.mode() === 'compass';
    var cur = view ? view.current() : { preset: 'std', tour: false };
    Array.prototype.forEach.call(viewsEl.querySelectorAll('[data-view]'), function (b) {
      var k = b.getAttribute('data-view'); b.setAttribute('aria-pressed', String(k === 'tour' ? !!cur.tour : k === cur.preset));
    });
  }
    return { mount: buildViews, sync: syncViews };
  }
  g.CLSkyDeepViews = { create: create };
})(window);
