(function (g) {
  'use strict';
  var doc = g.document;
  if (!doc) return;

  var cv = null, cx = null, host = null, ref = null, dpr = 1, W = 0, H = 0, on = false;
  var lastX = null, vSlot = 0;
  var st = { mounts: 0, draws: 0, hides: 0, w: 0, h: 0 };
  var SPAN = [3.4, 1.9], LIFT = 1.5;
  var TAILK = 0.16, TAILMAX = 9, TAILN = 14;

  function TK() { return g.CLSkyTokens; }
  function hex(n, a) {
    return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
  }

  function size(o) {
    var r = o.w > 0 ? o : host.getBoundingClientRect(), d = g.devicePixelRatio || 1;
    if (d > 2) d = 2;
    if ((r.w || r.width) === W && (r.h || r.height) === H && d === dpr) return;
    W = r.w > 0 ? r.w : r.width; H = r.h > 0 ? r.h : r.height; dpr = d;
    cv.width = Math.max(1, Math.round(W * dpr));
    cv.height = Math.max(1, Math.round(H * dpr));
    st.w = cv.width; st.h = cv.height;
  }

  function show(v) {
    if (v === on) return;
    on = v;
    cv.hidden = !v;
  }

  function mount(h, el) {
    if (!h) return;
    if (cv && host === h) { ref = el || ref; return; }
    if (cv && cv.parentNode) cv.parentNode.removeChild(cv);
    host = h; ref = el || null;
    cv = doc.createElement('canvas');
    cv.className = 'sky-dial-fx';
    cv.setAttribute('aria-hidden', 'true');
    cv.hidden = true;
    if (ref && ref.nextSibling) host.insertBefore(cv, ref.nextSibling); else host.appendChild(cv);
    cx = cv.getContext('2d');
    W = H = 0; on = false;
    st.mounts++;
  }

  function hide() {
    if (!cv) return;
    if (on) { cx.clearRect(0, 0, cv.width, cv.height); st.hides++; }
    show(false);
    lastX = null; vSlot = 0;
  }

  function tick(o, x, r0, r1, col, wpx) {
    var a = o.ang(x), p = o.pj(r0, a), q = o.pj(r1, a);
    if (!p || !q) return;
    cx.strokeStyle = col; cx.lineWidth = wpx;
    cx.beginPath(); cx.moveTo(p[0], p[1]); cx.lineTo(q[0], q[1]); cx.stroke();
  }

  function tail(o, x, dx, al) {
    var i, t0, t1, p, q, a;
    cx.lineCap = 'round';
    for (i = 0; i < TAILN; i++) {
      t0 = x + dx * i / TAILN; t1 = x + dx * (i + 1) / TAILN;
      if (t1 < -0.5 || t1 > o.n - 0.5) break;
      p = o.pj(o.rB, o.ang(t0)); q = o.pj(o.rB, o.ang(t1));
      if (!p || !q) continue;
      a = Math.pow(1 - i / TAILN, 1.7) * 0.5 * al;
      cx.strokeStyle = hex(TK().C.BRASS_HOT, a);
      cx.lineWidth = 2.4 * (1 - i / TAILN) + 0.5;
      cx.beginPath(); cx.moveTo(p[0], p[1]); cx.lineTo(q[0], q[1]); cx.stroke();
    }
    cx.lineCap = 'butt';
  }

  function draw(o) {
    var T = TK(), C, al, i, x, k, d, span, r0, r1, glow, p;
    if (!cv || !o || !T) return;
    C = T.C;
    al = +o.al || 0;
    if (!(al > 0.004) || o.slot == null && !o.hot) { hide(); return; }
    size(o); show(true);
    st.draws++;
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx.clearRect(0, 0, W, H);

    x = o.slot != null ? o.slot : (o.hot && o.hot.slot != null ? o.hot.slot : null);
    if (x == null) { hide(); return; }
    r0 = o.rB; r1 = o.rB + (o.tk || 0.03) * LIFT;
    span = SPAN[0] + (SPAN[1] - SPAN[0]) * (+o.gk || 0);

    if (!o.low) {
      p = o.pj(o.rB, o.ang(x)); d = o.pj(o.rB, o.ang(x + 1));
      var stp = p && d ? Math.max(1, Math.ceil(4 / Math.max(0.25, Math.hypot(p[0] - d[0], p[1] - d[1])))) : 1, x0 = Math.round(x / stp) * stp;
      k = Math.ceil(span * 2);
      for (i = -k; i <= k; i++) {
        d = Math.abs(i);
        glow = Math.exp(-(d * d) / (2 * span * span));
        if (glow < 0.03) continue;
        var xi = x0 + i * stp;
        if (xi < -0.5 || xi > o.n - 0.5) continue;
        tick(o, xi, r0, r1, hex(C.BRASS, (0.10 + 0.55 * glow) * al), 1 + 0.7 * glow);
      }
    }

    if (lastX != null && o.dt > 0) {
      vSlot += ((x - lastX) / o.dt - vSlot) * Math.min(1, o.dt / 0.08);
    }
    lastX = x;
    if (!o.low && !o.red && Math.abs(vSlot) > 0.8) {
      tail(o, x, Math.max(-TAILMAX, Math.min(TAILMAX, -vSlot * TAILK)), al);
    }

    tick(o, x, r0 - (o.tk || 0.03) * 0.45, r1 + (o.tk || 0.03) * 0.5,
      hex(o.drag ? C.BRASS_HOT : C.BRASS, (0.55 + 0.4 * (+o.gk || 0)) * al), o.drag ? 2.1 : 1.6);
    if (!o.low) {
      p = o.pj(o.rB, o.ang(x));
      if (p) {
        glow = cx.createRadialGradient(p[0], p[1], 0, p[0], p[1], 13 + 9 * (+o.gk || 0));
        glow.addColorStop(0, hex(C.BRASS_HOT, 0.38 * al));
        glow.addColorStop(1, hex(C.BRASS_HOT, 0));
        cx.fillStyle = glow;
        cx.beginPath(); cx.arc(p[0], p[1], 13 + 9 * (+o.gk || 0), 0, 6.2832); cx.fill();
      }
    }

    if (o.near && Math.abs(o.near(x) - x) > 0.15) tick(o, o.near(x), r0, r1, hex(C.BRASS_HOT, 0.75 * al), 1.3);
  }

  g.CLSkyDialFx = {
    mount: mount,
    draw: draw,
    hide: hide,
    stats: function () {
      return { fxMounted: !!cv, fxOn: on, fxDraws: st.draws, fxHides: st.hides, fxW: st.w, fxH: st.h, fxMounts: st.mounts, fxVel: +vSlot.toFixed(2), fxTail: +Math.min(TAILMAX, Math.abs(vSlot) * TAILK).toFixed(2) };
    }
  };
})(window);
