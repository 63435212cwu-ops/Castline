/*!
 * @role field
 * @owns js/sky/sky-field-avoid.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 团名的避让盒（CLSkyFieldAvoid，从 sky-field 拆出）：团名要让开的东西 = 已显示的星名（星名由场景的标签避让放好，团名是可以挪的那一方）+ 界面栏（含展开的分组卡面板）。
 * 逐帧路径不读布局：星名盒 = 它的 transform 平移 + 按「类名 | 字数」缓存的尺寸；界面栏盒与坐标原点 250 ms 缓存（相对星域层根元素）。
 * create(root, now) → { labels() 已显示星名, obstacles(labs) 盒 [x0, y0, x1, y1] 列表, sig(labs) 星名集合指纹, under(box, obs) 是否压在界面栏上 }
 */
(function (g) {
  'use strict';
  var HUD = '.sky-top,.skd-views:not([hidden]),.sky-bottom > *:not([hidden]),.skg-deck.is-on:not(.is-folded)';   /* 与星名同一份界面栏（sky-shell setHudSelector）：展开的分组卡面板也让开 */
  var TR = /translate(?:3d)?\(\s*(-?[\d.]+)px\s*,\s*(-?[\d.]+)px/;

  function create(root, now) {
    var host = null, cache = typeof WeakMap === 'function' ? new WeakMap() : null, hud = [], hudT = -1e9, orgX = 0, orgY = 0;
    function labels() {
      if (!host) host = document.getElementById('labels');
      var out = [], ch = host ? host.children : [];
      for (var i = 0; i < ch.length; i++) { var el = ch[i]; if (el.classList.contains('on') && el.classList.contains('cl-lab')) out.push(el); }
      return out;
    }
    function refresh() {
      var t = now(); if (t - hudT < 250) return; hudT = t;
      var o = root.getBoundingClientRect(), lr = host ? host.getBoundingClientRect() : o;
      orgX = lr.left - o.left; orgY = lr.top - o.top; hud = [];
      Array.prototype.forEach.call(document.querySelectorAll(HUD), function (el) { var r = el.getBoundingClientRect(); if (r.width > 2 && r.height > 2) hud.push([r.left - o.left - 6, r.top - o.top - 6, r.right - o.left + 6, r.bottom - o.top + 6]); });
    }
    function box(el) {
      var m = TR.exec(el.style.transform || ''); if (!m) return null;
      var key = el.className + '|' + el.textContent.length, c = cache ? cache.get(el) : null;
      if (!c || c.key !== key) { c = { key: key, w: el.offsetWidth, h: el.offsetHeight }; if (cache) cache.set(el, c); }
      if (c.w < 2 || c.h < 2) return null;
      var x = +m[1] + orgX, y = +m[2] + orgY;
      return [x - 2, y - 2, x + c.w + 2, y + c.h + 2];
    }
    function obstacles(labs) {
      refresh();
      var out = hud.slice();
      for (var i = 0; i < labs.length; i++) { var b = box(labs[i]); if (b) out.push(b); }
      out.hudN = hud.length; out.obsN = out.length;   /* [0, hudN) 界面栏 · [hudN, obsN) 星名；调用方之后追加的是已放好的团名 */
      return out;
    }
    /* 星名挪了 / 换了（镜头没动也会发生）→ 指纹变 → 团名重排 */
    function sig(labs) {
      var s = String(labs.length);
      for (var i = 0; i < labs.length; i++) s += labs[i].style.transform;
      return s;
    }
    /* 盒压在界面栏上（所有候选位都不空、只能留原位）→ 调用方把它淡到栏下，像星名一样不被栏边切一半 */
    function under(b, obs) {
      for (var i = 0; i < (obs.hudN || 0); i++) { var h = obs[i]; if (b[0] < h[2] && b[2] > h[0] && b[1] < h[3] && b[3] > h[1]) return true; }
      return false;
    }
    return { labels: labels, obstacles: obstacles, sig: sig, under: under };
  }

  g.CLSkyFieldAvoid = { create: create };
})(window);
