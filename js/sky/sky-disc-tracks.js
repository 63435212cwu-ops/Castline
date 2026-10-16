(function (g) {
  'use strict';
  function create(C) {
    function track(pts) {
      var cum = [0], j;
      for (j = 1; j < pts.length; j++) cum.push(cum[j - 1] + Math.hypot(pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]));
      return { P: pts, cum: cum, plen: cum[cum.length - 1] || 0, d: null };
    }
    function offsetPts(B, dist, mid) {
      var out = [], n = B.length, i;
      for (i = 0; i < n; i++) {
        var p = B[i], a = B[Math.max(0, i - 1)], b = B[Math.min(n - 1, i + 1)], tx = b[0] - a[0], ty = b[1] - a[1], L = Math.hypot(tx, ty) || 1, nx = -ty / L, ny = tx / L;
        if (mid && (mid[0] - p[0]) * nx + (mid[1] - p[1]) * ny < 0) { nx = -nx; ny = -ny; }
        out.push([p[0] + nx * dist, p[1] + ny * dist]);
      }
      return out;
    }
    function wOf(it) { return it.kind === 'main' ? C.MAIN_W : it.w; }
    function trackFor(it, side, ln) {
      ln = ln || 0;
      var key = side + 4 * ln;
      if (!it.tracks[key]) {
        if (side >= 2) it.tracks[key] = ln ? null : laneTrack(it, side === 2);
        else {
          var clearPx = wOf(it) / 2 + (it.kind === 'main' ? C.CLEAR_MAIN : C.CLEAR_NAMED) + it.fh * C.INK + (ln === 2 ? it.fh * (C.LINE_H || 1.22) : 0);
          it.tracks[key] = track(offsetPts(it.B, side === 0 ? (it.kind === 'main' ? -clearPx : clearPx) : -clearPx, it.mid));
        }
      }
      if (it.tracks[key]) it.tracks[key].shortSide = side;
      return it.tracks[key];
    }
    function laneTrack(it, after) {
      var aEnd = after ? it.a1 : it.a0, dir = after ? -1 : 1, p0 = C.projA(it.r, aEnd), p1 = C.projA(it.r, aEnd + dir * 0.02);
      if (!p0 || !p1) return null;
      var sp = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.02 || 1;
      var aS = aEnd + dir * (3.5 / sp), aE = aS + dir * ((it.tw + 2 * C.LAB_PAD + 10) / sp);
      var seam = after ? C.angle(C.M.nCh) : C.angle(0);
      if (after ? aE < seam : aE > seam) aE = seam;
      if (Math.abs(aE - aS) * sp < it.tw + 2 * C.LAB_PAD + 2) return null;
      var n = 10, cw = [], i;
      for (i = 0; i <= n; i++) { var a = after ? aS + (aE - aS) * i / n : aE + (aS - aE) * i / n, q = C.projA(it.r, a); if (q) cw.push(q); }
      if (cw.length < 2) return null;
      var T = track(cw), x = (it.tw / 2 + C.LAB_PAD + 2.5) / (T.plen || 1);
      T.fNear = after ? x : 1 - x;
      return T;
    }
    function at(T, d) {
      var c = T.cum, points = T.P, k = 1; if (!points || points.length < 2) return null;
      d = C.clamp(d, 0, T.plen);
      while (k < c.length - 1 && c[k] < d) k++;
      var t = (d - c[k - 1]) / Math.max(1e-6, c[k] - c[k - 1]);
      return [points[k - 1][0] + (points[k][0] - points[k - 1][0]) * t, points[k - 1][1] + (points[k][1] - points[k - 1][1]) * t];
    }
    function uprightTrack(it, T, f, two) {
      var tw = two ? it.tw2 || it.tw : it.tw, lh = two ? it.fh * (C.LINE_H || 1.22) : 0;
      var d = T.plen * f, half = Math.max(6, (tw || 24) / 2), a = at(T, d - half), b = at(T, d + half);
      if (!a || !b) return { T: T, f: f };
      var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
      if (Math.abs(dx) >= len * 0.88) return { T: T, f: f };
      var p = at(T, d), pad = half + C.LAB_PAD + 4;
      if (T.shortSide < 2 && it.mid) {
        var k = 1;
        while (k < T.cum.length - 1 && T.cum[k] < d) k++;
        var t = (d - T.cum[k - 1]) / Math.max(1e-6, T.cum[k] - T.cum[k - 1]), ta = it.B[k - 1], tb = it.B[k];
        var tx = tb[0] - ta[0], ty = tb[1] - ta[1], tl = Math.hypot(tx, ty) || 1;
        p = [ta[0] + tx * t, ta[1] + ty * t];
        var nx = -ty / tl, ny = tx / tl;
        if ((it.mid[0] - p[0]) * nx + (it.mid[1] - p[1]) * ny < 0) { nx = -nx; ny = -ny; }
        if (it.kind === 'main' || T.shortSide === 1) { nx = -nx; ny = -ny; }
        var ink = it.fh * C.INK + lh / 2, anx = Math.abs(nx), wproj = it.kind === 'main' ? anx : anx * anx,
          dist = wOf(it) / 2 + (it.kind === 'main' ? C.CLEAR_MAIN : C.CLEAR_NAMED) + ink * Math.abs(ny) + tw / 2 * wproj;
        p = [p[0] + nx * dist, p[1] + ny * dist];
      }
      if (two) return { T: track([[p[0] - pad, p[1] - lh / 2], [p[0] + pad, p[1] - lh / 2]]), T2: track([[p[0] - pad, p[1] + lh / 2], [p[0] + pad, p[1] + lh / 2]]), f: 0.5, horizontal: true };
      return { T: track([[p[0] - pad, p[1]], [p[0] + pad, p[1]]]), f: 0.5, horizontal: true };
    }
    function linePts(it, T, f, tw) {
      var mid = T.plen * f, half = tw / 2 + C.LAB_PAD, pts = [], i, steps = Math.max(6, Math.ceil(2 * half / 3));
      if (mid - half < 2 || mid + half > T.plen - 2) return null;
      for (i = 0; i <= steps; i++) { var p = at(T, mid - half + (2 * half) * i / steps); if (p) pts.push(p); }
      for (i = 0; i < pts.length; i++) if (pts[i][0] < C.LAB_PAD || pts[i][0] > C.Wv - C.LAB_PAD || pts[i][1] < it.fh || pts[i][1] > C.Hv - it.fh) return null;
      return pts;
    }
    function footprint(it, T, f) {
      var up = uprightTrack(it, T, f); T = up.T; f = up.f;
      var pts = linePts(it, T, f, it.tw); if (!pts) return null;
      if (up.horizontal) { var center = at(T, T.plen * f), ink = it.fh * C.INK; pts.inkBox = [center[0] - it.tw / 2, center[1] - ink, center[0] + it.tw / 2, center[1] + ink]; }
      return pts;
    }
    function shape2(it, side, f) {
      var Tn = trackFor(it, side, 1), Tf = trackFor(it, side, 2); if (!Tn || !Tf || !it.parts) return null;
      var up = uprightTrack(it, Tn, f, true);
      return up.horizontal ? { lines: [[up.T, 0.5], [up.T2, 0.5]], horizontal: true } : { lines: [[Tn, f], [Tf, f]], horizontal: false };
    }
    function footprint2(it, side, f) {
      var S = shape2(it, side, f); if (!S) return null;
      var tw = it.tw2 || it.tw, pts = [], i, q;
      for (i = 0; i < 2; i++) { q = linePts(it, S.lines[i][0], S.lines[i][1], tw); if (!q) return null; pts = pts.concat(q); }
      if (S.horizontal) {
        var a = at(S.lines[0][0], S.lines[0][0].plen / 2), b = at(S.lines[1][0], S.lines[1][0].plen / 2), ink = it.fh * C.INK;
        pts.inkBox = [a[0] - tw / 2, a[1] - ink, a[0] + tw / 2, b[1] + ink];
      }
      return pts;
    }
    function clash(a, b) {
      for (var i = 0; i < a.length; i++) for (var j = 0; j < b.length; j++) { var dx = a[i][0] - b[j][0], dy = a[i][1] - b[j][1]; if (dx * dx + dy * dy < C.LAB_GAP * C.LAB_GAP) return true; }
      return false;
    }
    function segD2(p, a, b) {
      var vx = b[0] - a[0], vy = b[1] - a[1], wx = p[0] - a[0], wy = p[1] - a[1], L = vx * vx + vy * vy, t = L > 0 ? C.clamp((wx * vx + wy * vy) / L, 0, 1) : 0;
      var dx = wx - vx * t, dy = wy - vy * t; return dx * dx + dy * dy;
    }
    function segBox(a, b, box) {
      var lo = 0, hi = 1;
      for (var axis = 0; axis < 2; axis++) {
        var v = b[axis] - a[axis], min = box[axis], max = box[axis + 2];
        if (Math.abs(v) < 1e-6) { if (a[axis] < min || a[axis] > max) return false; continue; }
        var t0 = (min - a[axis]) / v, t1 = (max - a[axis]) / v;
        lo = Math.max(lo, Math.min(t0, t1)); hi = Math.min(hi, Math.max(t0, t1));
        if (lo > hi) return false;
      }
      return true;
    }
    function segBoxD2(a, b, box) {
      if (segBox(a, b, box)) return 0;
      var ax = Math.max(box[0] - a[0], a[0] - box[2], 0), ay = Math.max(box[1] - a[1], a[1] - box[3], 0);
      var bx = Math.max(box[0] - b[0], b[0] - box[2], 0), by = Math.max(box[1] - b[1], b[1] - box[3], 0), best = Math.min(ax * ax + ay * ay, bx * bx + by * by);
      for (var i = 0; i < 4; i++) best = Math.min(best, segD2([box[i % 2 ? 2 : 0], box[i < 2 ? 1 : 3]], a, b));
      return best;
    }
    function arcClash(fp, it) { var items = C.items;
      var bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity, i, j, k;
      for (i = 0; i < fp.length; i++) { bx0 = Math.min(bx0, fp[i][0]); bx1 = Math.max(bx1, fp[i][0]); by0 = Math.min(by0, fp[i][1]); by1 = Math.max(by1, fp[i][1]); }
      if (fp.inkBox) { bx0 = fp.inkBox[0]; by0 = fp.inkBox[1]; bx1 = fp.inkBox[2]; by1 = fp.inkBox[3]; }
      for (k = 0; k < items.length; k++) {
        var c = items[k]; if (c.kind === 'quiet' || !c.bb || c.Q.length < 2) continue;
        var pad = (fp.inkBox ? 0 : it.fh * C.INK) + c.w / 2 + (c.kind === 'main' ? 1.6 : 0.8);
        if (c.bb[0] - pad > bx1 || c.bb[2] + pad < bx0 || c.bb[1] - pad > by1 || c.bb[3] + pad < by0) continue;
        var pad2 = pad * pad, Q = c.Q;
        if (fp.inkBox) { for (j = 1; j < Q.length; j++) if (segBoxD2(Q[j - 1], Q[j], fp.inkBox) < pad2) return true; continue; }
        for (i = 0; i < fp.length; i++) for (j = 1; j < Q.length; j++) if (segD2(fp[i], Q[j - 1], Q[j]) < pad2) return true;
      }
      return false;
    }
    return { track: track, trackFor: trackFor, at: at, uprightTrack: uprightTrack, footprint: footprint, footprint2: footprint2, shape2: shape2, clash: clash, arcClash: arcClash };
  }
  g.CLSkyDiscTracks = { create: create };
})(window);
