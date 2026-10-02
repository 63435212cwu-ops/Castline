/*!
 * @role rain
 * @owns js/sky/sky-rain.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 *
 * 字符数据流（参考开篇的字符雨，换成这部书自己的字）：竖列字符下落，列头亮、尾巴渐隐；两层景深（近列大而快、远列小而慢）。
 * 读完材料前只用数字与星号作占位（装饰，不冒充数据）；glyphs() 换上书中人名 / 章回编号之后，每列就是几段真名竖排落下
 * （正在落的列当场换字，读完材料那一刻整片雨「解码」成这部书）。
 * converge()：一批真实文字（事件名 / 关系人名）从四周飞向一点汇聚——罗盘开启时「数据流入晶体」。
 *
 * 纪律：ES5；不开 rAF / setInterval——每列一次性 Web Animations（transform 走合成层，主线程被建图占满时照样流）；
 * 列元素池化复用（≤ 96 列、≤ 48 条汇聚流），DOM 恒定；减弱动效 / low 档不下雨。
 */
(function (g) {
  'use strict';
  var U = g.CLSkyUtil;
  var PH = '0123456789✦⋆∗·';
  var POOL = 96, STREAMS = 48;

  function R() {
    var o = g.CLSkyTokens && g.CLSkyTokens.OPEN;
    return (o && o.rain) || { cols: 44, near: 0.34, far: 0.16, len: [10, 26], dur: [1.6, 3.4], every: 1.1 };
  }
  function rnd(a, b) { return a + Math.random() * (b - a); }

  function mount(host, opts) {
    opts = opts || {};
    var root = U.mk('div', 'skd-rain' + (opts.cls ? ' ' + opts.cls : ''), host || g.document.body);
    root.setAttribute('aria-hidden', 'true');
    var cols = [], streams = [], words = null, tier = 'high', active = 0, spawned = 0, flows = 0, lastWave = -1e9, dead = false;

    function text(n) {
      var out = [], guard = 0, w, k;
      if (!words || !words.length) {
        for (k = 0; k < n; k++) out.push(PH.charAt(Math.floor(Math.random() * PH.length)));
        return out.join('\n');
      }
      while (out.length < n && guard++ < 60) {
        w = U.chars(words[Math.floor(Math.random() * words.length)]);
        for (k = 0; k < w.length && out.length < n; k++) out.push(w[k]);
        if (out.length < n) out.push('·');
      }
      return out.join('\n');
    }
    function freeCol() {
      for (var i = 0; i < cols.length; i++) if (!cols[i].busy) return cols[i];
      if (cols.length >= POOL) return null;
      var c = { el: U.mk('div', 'skd-rain__col', root), busy: false, anim: null };
      cols.push(c); return c;
    }
    function off() { return dead || tier === 'low' || U.reduced() || !root.animate; }

    /* 一波：按视口宽等比的列数，随机错峰落下；返回本波列数 */
    function wave(k) {
      if (off()) return 0;
      var r = R(), W = g.innerWidth || 1440, H = g.innerHeight || 900;
      var n = k || Math.round(U.clamp(r.cols * W / 1440, 12, 72)), step = W / n, made = 0, i, c, near, len, dur;
      for (i = 0; i < n; i++) {
        c = freeCol(); if (!c) break;
        near = Math.random() < 0.38; len = Math.round(rnd(r.len[0], r.len[1]));
        c.el.className = 'skd-rain__col' + (near ? ' is-near' : ' is-far') + (Math.random() < 0.14 ? ' is-brass' : '');
        c.el.textContent = text(len);
        c.el.style.setProperty('--x', Math.round(i * step + rnd(0.15, 0.85) * step) + 'px');
        dur = near ? rnd(r.dur[0], (r.dur[0] + r.dur[1]) / 2) : rnd((r.dur[0] + r.dur[1]) / 2, r.dur[1]);
        if (c.anim) c.anim.cancel();
        c.busy = true; active++; spawned++; made++;
        c.anim = c.el.animate([{ transform: 'translate3d(0,-100%,0)' }, { transform: 'translate3d(0,' + Math.round(H * 1.02) + 'px,0)' }],
          { duration: Math.round(dur * 1000), delay: Math.round(rnd(0, 1.2) * 1000), easing: 'linear', fill: 'both' });
        c.anim.onfinish = (function (cc) { return function () { if (cc.busy) { cc.busy = false; active--; } }; })(c);
      }
      lastWave = U.now();
      return made;
    }
    /* 距上一波不足 every 秒就不叠（阶段推进很快时不堆成一片） */
    function pulse() { var r = R(); return U.now() - lastWave >= r.every ? wave() : 0; }

    /* 汇聚：items = 真实文字；从以 (x, y) 为心、半径 ~0.46·min(W,H) 的圆周飞入并收束淡出。返回流数 */
    function converge(items, x, y, o) {
      o = o || {};
      if (off() || !items || !items.length) return 0;
      var W = g.innerWidth || 1440, H = g.innerHeight || 900, rad = Math.min(W, H) * (o.r || 0.46), n = Math.min(STREAMS, items.length), made = 0, i, s, a, sx, sy, deg;
      for (i = 0; i < n; i++) {
        s = null;
        for (var j = 0; j < streams.length; j++) if (!streams[j].busy) { s = streams[j]; break; }
        if (!s) { if (streams.length >= STREAMS) break; s = { el: U.mk('div', 'skd-rain__flow', root), busy: false, anim: null }; streams.push(s); }
        a = (i / n) * Math.PI * 2 + rnd(-0.25, 0.25);
        sx = Math.cos(a) * rad * rnd(0.85, 1.15); sy = Math.sin(a) * rad * rnd(0.7, 1.05);
        deg = Math.atan2(-sy, -sx) * 180 / Math.PI;
        s.el.textContent = String(items[i]);
        s.el.className = 'skd-rain__flow' + (i % 5 === 0 ? ' is-brass' : '');
        s.el.style.setProperty('--x', Math.round(x) + 'px'); s.el.style.setProperty('--y', Math.round(y) + 'px');
        if (s.anim) s.anim.cancel();
        s.busy = true; made++; flows++;
        s.anim = s.el.animate([
          { transform: 'translate3d(' + sx.toFixed(1) + 'px,' + sy.toFixed(1) + 'px,0) rotate(' + deg.toFixed(1) + 'deg) scale(1)', opacity: 0 },
          { opacity: 1, offset: 0.25 },
          { opacity: 0.9, offset: 0.7 },
          { transform: 'translate3d(0,0,0) rotate(' + deg.toFixed(1) + 'deg) scale(0.35)', opacity: 0 }
        ], { duration: Math.round(rnd(0.9, 1.35) * 1000 * (o.k || 1)), delay: Math.round((i / n) * 420 * (o.k || 1) + rnd(0, 120)), easing: 'cubic-bezier(.5,0,.2,1)', fill: 'both' });
        s.anim.onfinish = (function (ss) { return function () { ss.busy = false; }; })(s);
      }
      return made;
    }

    /* 回目只留编号（「第一章 牢狱之灾」→「第一章」）：契约 O1 = 书中人名 ∪ 章回数字，回目里的标题字不进雨 */
    var CH = /^第[^\s章回节卷部篇集]{1,8}[章回节卷部篇集]/;
    function glyphs(list) {
      var w = [], i, t, m, n;
      for (i = 0; list && i < list.length && w.length < 120; i++) {
        t = String(list[i] == null ? '' : list[i]).replace(/^\s+/, ''); m = CH.exec(t);
        t = (m ? m[0] : t).replace(/\s+/g, ''); if (t) w.push(t.slice(0, 12));
      }
      words = w.length ? w : null;
      /* 读完材料那一刻，正在落的列就地换上书里的字：行数不变 → 列高不变，合成层上的下落不跳 */
      for (i = 0; words && i < cols.length; i++) if (cols[i].busy) { n = cols[i].el.textContent.split('\n').length; cols[i].el.textContent = text(n); }
      return words ? words.length : 0;
    }
    function clear() {
      var i;
      for (i = 0; i < cols.length; i++) { if (cols[i].anim) cols[i].anim.cancel(); cols[i].busy = false; }
      for (i = 0; i < streams.length; i++) { if (streams[i].anim) streams[i].anim.cancel(); streams[i].busy = false; }
      active = 0;
    }
    function sample(k) {
      var out = [];
      for (var i = 0; i < cols.length && out.length < (k || 6); i++) if (cols[i].busy) out.push(cols[i].el.textContent.replace(/\n/g, ''));
      return out;
    }
    function setTier(t) { tier = t || 'high'; if (tier === 'low') clear(); }
    function dispose() { dead = true; clear(); if (root.parentNode) root.parentNode.removeChild(root); }
    function stats() {
      var run = 0, fl = 0, i;
      for (i = 0; i < cols.length; i++) if (cols[i].busy) run++;
      for (i = 0; i < streams.length; i++) if (streams[i].busy) fl++;
      return { cols: run, pool: cols.length, spawned: spawned, words: words ? words.length : 0, flows: fl, flowed: flows, sample: sample(4) };
    }
    return { el: root, wave: wave, pulse: pulse, converge: converge, glyphs: glyphs, clear: clear, setTier: setTier, dispose: dispose, stats: stats };
  }

  g.CLSkyRain = { mount: mount };
})(window);
