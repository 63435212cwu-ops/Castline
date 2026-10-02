/* @role scale · @owns js/sky/sky-scale.js · @budget drawcalls<=1 · passes<=1 · points/vertices/rtpx n/a · budget.kb<=12 · @contract deep-sky/1 */
(function (g) {
  'use strict';

  function tok() { return g.CLSkyTokens || null; }

  function num(v, dflt) {
    return (typeof v === 'number' && isFinite(v)) ? v : dflt;
  }

  function dpr() {
    var d = num(g.devicePixelRatio, 1);
    if (!isFinite(d) || d <= 0) d = 1;
    return d > 2 ? 2 : d;
  }

  function mount(host, opts) {
    var T = tok();
    var canvas = document.createElement('canvas');
    canvas.className = 'skd-scale__canvas';
    var ctx = canvas.getContext ? canvas.getContext('2d') : null;
    var geom = null, dirty = true;
    var st = {
      nCh: 1, mains: [], density: [], keys: [], max: 0,
      cursor: null, w: 0, h: 0, d: 1, ro: null, onWin: null, dead: false
    };

    if (host && host.appendChild) host.appendChild(canvas);

    function apply(o) {
      var n, i, v, mx, d, m, a, s, e, k, tmp;
      if (!o) return;
      dirty = true;
      n = Math.floor(num(o.nCh, 0));
      st.nCh = (isFinite(n) && n > 0) ? n : 1;
      n = st.nCh;
      d = [];
      mx = 0;
      if (o.density && o.density.length) {
        for (i = 0; i < n; i++) {
          v = num(o.density[i], 0);
          if (v < 0) v = 0;
          d.push(v);
          if (v > mx) mx = v;
        }
      }
      st.density = d;
      st.max = mx;
      m = [];
      if (o.mains && o.mains.length) {
        for (i = 0; i < o.mains.length; i++) {
          a = o.mains[i];
          if (!a) continue;
          s = Math.floor(num(a.c0, NaN));
          e = Math.floor(num(a.c1, NaN));
          if (!isFinite(s) || !isFinite(e)) continue;
          if (s < 0) s = 0;
          if (e > n - 1) e = n - 1;
          if (e < s) { tmp = s; s = e; e = tmp; }
          m.push({ c0: s, c1: e, color: num(a.color, 0) });
        }
      }
      st.mains = m;
      k = [];
      if (o.keys && o.keys.length) {
        for (i = 0; i < o.keys.length; i++) {
          v = Math.floor(num(o.keys[i], NaN));
          if (isFinite(v) && v >= 0 && v < n) k.push(v);
        }
      }
      st.keys = k;
      if (o.cursor !== undefined) {
        st.cursor = (typeof o.cursor === 'number' && isFinite(o.cursor)) ? o.cursor : null;
      }
    }

    function measure() {
      var d = dpr();
      /* 尺寸取 ResizeObserver 记下的值：拨盘拖动中每帧重画，逐帧读 clientWidth 会在别的层改完 DOM 后强制排版 */
      var w = st.cw != null ? st.cw : canvas.clientWidth | 0;
      var h = st.ch != null ? st.ch : canvas.clientHeight | 0;
      var cw, ch;
      if (w <= 0 || h <= 0) return false;
      cw = Math.round(w * d);
      ch = Math.round(h * d);
      if (canvas.width !== cw) canvas.width = cw;
      if (canvas.height !== ch) canvas.height = ch;
      st.w = w;
      st.h = h;
      st.d = d;
      if (ctx.setTransform) ctx.setTransform(d, 0, 0, d, 0, 0);
      return true;
    }

    /* 只缓存坐标：所有 Canvas 绘制仍在原 context、按原顺序执行。 */
    function geometry(W, H, d, n) {
      var q = { w: W, h: H, d: d, bars: [], mains: [], keys: [] };
      var i, v, hgt, bw, by, mm, x0, x1, kx, ky, kd;
      by = q.by = Math.round(H * 0.72 * d) / d;
      bw = W / n - 1; if (bw < 1) bw = 1;
      if (st.max > 0) for (i = 0; i < st.density.length; i++) {
        v = st.density[i]; if (!v) continue;
        hgt = Math.sqrt(v / st.max) * H * 0.5;
        if (hgt < 1 / d) hgt = 1 / d;
        q.bars.push(Math.round((i + 0.5) / n * W * d) / d - bw / 2, by - hgt, bw, hgt);
      }
      for (i = 0; i < st.mains.length; i++) {
        mm = st.mains[i];
        x0 = Math.round((mm.c0 / n * W) * d) / d + 0.5;
        x1 = Math.round(((mm.c1 + 1) / n * W) * d) / d - 0.5;
        if (x1 - x0 < 0.5) x1 = x0 + 0.5;
        q.mains.push(x0, by + 1, x1 - x0, 3 / d);
      }
      kd = 1 / d; ky = by - 5 / d;
      for (i = 0; i < st.keys.length; i++) {
        kx = Math.round((st.keys[i] + 0.5) / n * W * d) / d;
        q.keys.push(kx, ky - kd, kx + kd, ky, kx, ky + kd, kx - kd, ky);
      }
      dirty = false; geom = q; return q;
    }

    function draw() {
      var W, H, d, n, C, i, j, q, by, x, mm, c;
      if (st.dead || !ctx) return;
      if (!T) T = tok();
      if (!T) return;
      if (!measure()) return;
      W = st.w; H = st.h; d = st.d; n = st.nCh; C = T.C;
      q = !geom || dirty || geom.w !== W || geom.h !== H || geom.d !== d ? geometry(W, H, d, n) : geom;
      ctx.clearRect(0, 0, W, H);
      ctx.lineCap = 'butt';
      ctx.lineJoin = 'miter';
      by = q.by;

      ctx.globalAlpha = 0.35;
      ctx.strokeStyle = T.hexCss(C.INK3);
      ctx.lineWidth = 1 / d;
      ctx.beginPath();
      ctx.moveTo(0, by);
      ctx.lineTo(W, by);
      ctx.stroke();

      if (st.max > 0 && st.density.length) {
        ctx.globalAlpha = 0.28;
        ctx.fillStyle = T.hexCss(C.INK2);
        for (i = 0; i < q.bars.length; i += 4) {
          ctx.fillRect(q.bars[i], q.bars[i + 1], q.bars[i + 2], q.bars[i + 3]);
        }
      }

      if (st.mains.length) {
        ctx.globalAlpha = 0.85;
        for (i = 0; i < st.mains.length; i++) {
          mm = st.mains[i];
          j = i * 4;
          ctx.fillStyle = T.hexCss(mm.color);
          ctx.fillRect(q.mains[j], q.mains[j + 1], q.mains[j + 2], q.mains[j + 3]);
        }
      }

      if (st.keys.length) {
        ctx.globalAlpha = 0.8;
        ctx.fillStyle = T.hexCss(C.BRASS);
        for (i = 0; i < q.keys.length; i += 8) {
          ctx.beginPath();
          ctx.moveTo(q.keys[i], q.keys[i + 1]);
          ctx.lineTo(q.keys[i + 2], q.keys[i + 3]);
          ctx.lineTo(q.keys[i + 4], q.keys[i + 5]);
          ctx.lineTo(q.keys[i + 6], q.keys[i + 7]);
          ctx.closePath();
          ctx.fill();
        }
      }

      c = st.cursor;
      if (c !== null && c >= 0 && c < n) {
        x = Math.round((c + 0.5) / n * W * d) / d;
        ctx.globalAlpha = 0.10;
        ctx.fillStyle = T.hexCss(C.BRASS);
        ctx.fillRect(0, 0, x, H);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = T.hexCss(C.BRASS_HOT);
        ctx.lineWidth = 1.5 / d;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
        ctx.shadowBlur = 8 * d;
        ctx.shadowColor = T.hexCss(C.BRASS_HOT);
        ctx.fillStyle = T.hexCss(C.BRASS_HOT);
        ctx.beginPath();
        ctx.arc(x, 6 / d, 3 / d, 0, 6.283185307179586);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.shadowColor = 'rgba(0,0,0,0)';
      }

      ctx.globalAlpha = 1;
    }

    function update(o) {
      if (st.dead) return;
      apply(o);
      draw();
    }

    function setCursor(c) {
      if (st.dead) return;
      st.cursor = (typeof c === 'number' && isFinite(c)) ? c : null;
      draw();
    }

    function destroy() {
      st.dead = true;
      if (st.ro) { st.ro.disconnect(); st.ro = null; }
      if (st.onWin) { g.removeEventListener('resize', st.onWin, false); st.onWin = null; }
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      st.mains = []; st.density = []; st.keys = [];
      st.w = 0; st.h = 0; geom = null;
    }

    if (g.ResizeObserver) {
      st.ro = new g.ResizeObserver(function (en) {
        var r = en && en[0] && en[0].contentRect;
        if (r) { st.cw = r.width | 0; st.ch = r.height | 0; }
        draw();
      });
      st.ro.observe(canvas);
    } else {
      st.onWin = function () { draw(); };
      g.addEventListener('resize', st.onWin, false);
    }

    apply(opts);
    draw();

    return { update: update, setCursor: setCursor, destroy: destroy, el: canvas };
  }

  g.CLSkyScale = { mount: mount };

})(window);
