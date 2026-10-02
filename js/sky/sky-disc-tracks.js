/**
 * @role component
 * @owns js/sky/sky-disc-tracks.js
 * 字轨、正立投影与字身和彩弧碰撞检测；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    function track(pts) {
      var cum = [0], j;
      for (j = 1; j < pts.length; j++) cum.push(cum[j - 1] + Math.hypot(pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]));
      return { P: pts, cum: cum, plen: cum[cum.length - 1] || 0, d: null };
    }
    /* dist > 0 → 向盘心（凸曲线上内法向与「指向盘内任一点」同号，逐点判向即可） */
    function offsetPts(B, dist, mid) {
      var out = [], n = B.length, i;
      for (i = 0; i < n; i++) {
        var p = B[i], a = B[Math.max(0, i - 1)], b = B[Math.min(n - 1, i + 1)], tx = b[0] - a[0], ty = b[1] - a[1], L = Math.hypot(tx, ty) || 1, nx = -ty / L, ny = tx / L;
        if (mid && (mid[0] - p[0]) * nx + (mid[1] - p[1]) * ny < 0) { nx = -nx; ny = -ny; }
        out.push([p[0] + nx * dist, p[1] + ny * dist]);
      }
      return out;
    }
    /* 字轨四种：0 = 弧内侧（支线）/ 弧外侧（主线）· 1 = 支线弧外侧 · 2 = 同车道接在弧尾之后 · 3 = 同车道接在弧头之前。
     * 2 / 3 是车道收窄后的退路：名字写在自己车道的空白里、紧贴自己的弧端，像线路图的端点站名，仍不压任何彩色弧。 */
    function trackFor(it, side) {
      if (!it.tracks[side]) {
        if (side >= 2) it.tracks[side] = laneTrack(it, side === 2);
        else {
          var clearPx = it.w / 2 + (it.kind === 'main' ? C.CLEAR_MAIN : C.CLEAR_NAMED) + it.fh * C.INK;
          it.tracks[side] = track(offsetPts(it.B, side === 0 ? (it.kind === 'main' ? -clearPx : clearPx) : -clearPx, it.mid));
        }
      }
      if (it.tracks[side]) it.tracks[side].shortSide = side;
      return it.tracks[side];
    }
    function laneTrack(it, after) {
      var aEnd = after ? it.a1 : it.a0, dir = after ? -1 : 1, p0 = C.projA(it.r, aEnd), p1 = C.projA(it.r, aEnd + dir * 0.02);
      if (!p0 || !p1) return null;
      var sp = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.02 || 1;
      var aS = aEnd + dir * (5 / sp), aE = aS + dir * ((it.tw + 2 * C.LAB_PAD + 12) / sp);
      /* 不越过时间尺两端（12 点方向的首尾缝） */
      if (after ? aE < C.angle(C.M.nCh) : aE > C.angle(0)) return null;
      var n = 10, cw = [], i;
      for (i = 0; i <= n; i++) { var a = after ? aS + (aE - aS) * i / n : aE + (aS - aE) * i / n, q = C.projA(it.r, a); if (q) cw.push(q); }
      if (cw.length < 2) return null;
      var T = track(cw), x = (it.tw / 2 + C.LAB_PAD + 2.5) / (T.plen || 1);
      T.fNear = after ? x : 1 - x;   /* 名字贴着弧端那一头（字轨一律顺时针存，朝向到落字时再定） */
      return T;
    }
    /* 名字避让：主线段名优先，其次具名支线按排名。支线名先在弧内侧沿弧滑动找空位（不压别的名字、不压别的彩色弧），
     * 内侧都被占 → 同车道接在弧尾 / 弧头 → 弧外侧；仍无空位就收起（悬停时照样显示，卡片也写名字）。 */
    function at(T, d) {
      var c = T.cum, points = T.P, k = 1; if (!points || points.length < 2) return null;
      d = C.clamp(d, 0, T.plen);
      while (k < c.length - 1 && c[k] < d) k++;
      var t = (d - c[k - 1]) / Math.max(1e-6, c[k] - c[k - 1]);
      return [points[k - 1][0] + (points[k][0] - points[k - 1][0]) * t, points[k - 1][1] + (points[k][1] - points[k - 1][1]) * t];
    }
    /* 陡字轨改正立短签：同一真实锚点，避让与绘制共用；给二期<30°留出曲率余量。 */
    function uprightTrack(it, T, f) {
      var d = T.plen * f, half = Math.max(6, (it.tw || 24) / 2), a = at(T, d - half), b = at(T, d + half);
      if (!a || !b) return { T: T, f: f };
      var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
      if (Math.abs(dx) >= len * 0.88) return { T: T, f: f };
      var p = at(T, d), pad = half + C.LAB_PAD + 4;
      /* 曲字变横字后，横向半字宽也要让开自己的彩弧；端点车道已在弧外空白，无需额外侧推。 */
      if (T.shortSide < 2 && it.mid) p[0] += (p[0] < it.mid[0] ? -1 : 1) * (it.kind === 'main' || T.shortSide === 1 ? 1 : -1) * pad;
      return { T: track([[p[0] - pad, p[1]], [p[0] + pad, p[1]]]), f: 0.5 };
    }
    function footprint(it, T, f) {
      var up = uprightTrack(it, T, f); T = up.T; f = up.f;
      var mid = T.plen * f, half = it.tw / 2 + C.LAB_PAD, pts = [], i, steps = Math.max(6, Math.ceil(2 * half / 3));
      if (mid - half < 2 || mid + half > T.plen - 2) return null;
      for (i = 0; i <= steps; i++) { var p = at(T, mid - half + (2 * half) * i / steps); if (p) pts.push(p); }
      for (i = 0; i < pts.length; i++) if (pts[i][0] < C.LAB_PAD || pts[i][0] > C.Wv - C.LAB_PAD || pts[i][1] < it.fh || pts[i][1] > C.Hv - it.fh) return null;
      return pts;
    }
    /* 两个字名的最小间距：字身之外还要有 3px 的深空缝，否则两串字读起来会黏成一句 */
    function clash(a, b) {
      for (var i = 0; i < a.length; i++) for (var j = 0; j < b.length; j++) { var dx = a[i][0] - b[j][0], dy = a[i][1] - b[j][1]; if (dx * dx + dy * dy < C.LAB_GAP * C.LAB_GAP) return true; }
      return false;
    }
    function segD2(p, a, b) {
      var vx = b[0] - a[0], vy = b[1] - a[1], wx = p[0] - a[0], wy = p[1] - a[1], L = vx * vx + vy * vy, t = L > 0 ? C.clamp((wx * vx + wy * vy) / L, 0, 1) : 0;
      var dx = wx - vx * t, dy = wy - vy * t; return dx * dx + dy * dy;
    }
    /* 名字的字身（中线 ± 字高一半）离任何别的主线 / 具名弧的边缘都要留出空隙；细纹是纹理，字的深空描边可以盖住它 */
    function arcClash(fp, it) { var items = C.items;
      var bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity, i, j, k;
      for (i = 0; i < fp.length; i++) { bx0 = Math.min(bx0, fp[i][0]); bx1 = Math.max(bx1, fp[i][0]); by0 = Math.min(by0, fp[i][1]); by1 = Math.max(by1, fp[i][1]); }
      for (k = 0; k < items.length; k++) {
        var c = items[k]; if (c.kind === 'quiet' || !c.bb || c.Q.length < 2) continue;
        var pad = it.fh * C.INK + c.w / 2 + (c.kind === 'main' ? 1.6 : 0.8);   /* 逐3px检查整段字身，具名弧也留出净空。 */
        if (c.bb[0] - pad > bx1 || c.bb[2] + pad < bx0 || c.bb[1] - pad > by1 || c.bb[3] + pad < by0) continue;
        var pad2 = pad * pad, Q = c.Q;
        for (i = 0; i < fp.length; i++) for (j = 1; j < Q.length; j++) if (segD2(fp[i], Q[j - 1], Q[j]) < pad2) return true;
      }
      return false;
    }
    return { track: track, trackFor: trackFor, at: at, uprightTrack: uprightTrack, footprint: footprint, clash: clash, arcClash: arcClash };
  }
  g.CLSkyDiscTracks = { create: create };
})(window);
