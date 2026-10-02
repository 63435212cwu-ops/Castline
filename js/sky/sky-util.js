/*!
 * @role util
 * @owns js/sky/sky-util.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 *
 * 星空层公共小工具：mk / svg / esc / clamp / now（秒）/ nowMs（毫秒）/ reduced / rgb / spring / type。
 * ES5；不开 rAF / setInterval；打字全靠 CSS 动画（每字一个 span，--i 递增延迟），主线程忙时照样打。
 */
(function (g) {
  'use strict';
  var doc = g.document, NS = 'http://www.w3.org/2000/svg';

  function mk(tag, cls, parent, text, owner) {
    var d = owner || (parent && parent.ownerDocument) || doc, e = d.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = String(text);
    if (parent) parent.appendChild(e);
    return e;
  }
  function svg(tag, cls, parent, text) {
    var d = (parent && parent.ownerDocument) || doc, e = d.createElementNS(NS, tag);
    if (cls) e.setAttribute('class', cls);
    if (text != null) e.textContent = String(text);
    if (parent) parent.appendChild(e);
    return e;
  }
  function esc(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function nowMs(fallback) { return g.performance && g.performance.now ? g.performance.now() : fallback != null ? fallback : Date.now(); }
  function now() { return nowMs() / 1000; }
  function mediaReduced() {
    try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function reduced() {
    var T = g.CLSkyTokens;
    return T && T.reduced ? !!T.reduced() : mediaReduced();
  }
  /* out 可复用数组 / Float32Array，逐帧写色不额外分配。 */
  function rgb(hex, out) {
    out = out || [0, 0, 0];
    out[0] = ((hex >> 16) & 255) / 255; out[1] = ((hex >> 8) & 255) / 255; out[2] = (hex & 255) / 255;
    return out;
  }
  /* 千分位：1184 → 1,184（日志里的真实计数） */
  function num(n) { n = Math.round(+n || 0); return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  /* 按字切分（含代理对），ES5 无 Array.from */
  function chars(t) { return String(t == null ? '' : t).match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[\s\S]/g) || []; }

  /* 阻尼弹簧一步（半隐式欧拉）：x 位置、v 速度、to 目标、w 角频率、z 阻尼比 → 写回 s.x / s.v */
  function spring(s, to, w, z, dt) {
    var a = -w * w * (s.x - to) - 2 * z * w * s.v;
    s.v += a * dt; s.x += s.v * dt;
    return s;
  }

  /**
   * 逐字打出：el 的每个字一个 span（.skd-type__c，--i 为序号），整体节拍由 CSS 变量驱动：
   *   --type-dt 每字间隔 · --type-d0 起始延迟 · --type-tt 打完时刻（掠光 / 光标从这一刻开始）。
   * o: { cps 每秒字数, delay 起始秒, glint 打完掠光, caret 行尾块光标, cls 附加类 }
   * 返回打完所需秒数；减弱动效直接写全文（返回 0）。textContent 始终等于原文。
   */
  function type(el, text, o) {
    o = o || {};
    var list = chars(text), cps = o.cps || 12.5, d0 = o.delay || 0, i, s;
    el.textContent = '';
    el.classList.remove('is-glint', 'has-caret', 'is-typed');
    if (reduced() || o.instant) {
      el.textContent = String(text == null ? '' : text);
      el.classList.add('is-typed');
      if (o.caret) el.classList.add('has-caret');
      return 0;
    }
    el.classList.add('skd-type');
    if (o.cls) el.classList.add(o.cls);
    var tt = d0 + list.length / cps;
    el.style.setProperty('--type-dt', (1 / cps).toFixed(4) + 's');
    el.style.setProperty('--type-d0', d0.toFixed(3) + 's');
    el.style.setProperty('--type-tt', tt.toFixed(3) + 's');
    var frag = doc.createDocumentFragment();
    for (i = 0; i < list.length; i++) {
      s = doc.createElement('span');
      s.className = 'skd-type__c';
      s.style.setProperty('--i', String(i));
      s.textContent = list[i];
      frag.appendChild(s);
    }
    el.appendChild(frag);
    if (o.glint) el.classList.add('is-glint');
    if (o.caret) el.classList.add('has-caret');
    return tt;
  }

  g.CLSkyUtil = { mk: mk, svg: svg, esc: esc, clamp: clamp, now: now, nowMs: nowMs, mediaReduced: mediaReduced, reduced: reduced, rgb: rgb, num: num, chars: chars, spring: spring, type: type };
})(window);
