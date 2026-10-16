(function (g) {
  'use strict';
  function create(C) {
    /* 光层在时，弧 / 珠 / 刻度 / 外环的 SVG 都是透明的（只留字与命中）：不写它们的几何；
       镜头运动中细支（无字）与所有命中路径都不重算，停稳 140 ms 后补一次全量（大书 1400 条路径逐帧重写曾占旋转帧 10%） */
    function farFade() { var E = C.E, items = C.items;
      if (!E) return;
      var wc = E[15]; if (!(wc > 1e-6)) return;
      for (var i = 0; i < items.length; i++) {
        var it = items[i]; if (!it.tx) continue;
        var am = (it.a0 + it.a1) / 2, w = E[3] * it.r * Math.cos(am) + E[7] * it.r * Math.sin(am) + E[11] * C.zAt(it.r) + wc;
        var fk = C.clamp(((w - wc) / wc - 0.10) / 0.10, 0, 1), fo = (1 - 0.45 * fk).toFixed(2);
        if (it.fo !== fo) { it.fo = fo; it.tx.setAttribute('fill-opacity', fo); it.tx.setAttribute('stroke-opacity', fo); }
      }
    }
    function measureText() {
      var probes = [];
      C.items.forEach(function (it) {
        if (!it.tx || it.numberBounds || !it.tx.cloneNode) return;
        var el = it.tx.cloneNode(false);
        el.textContent = it.tx.textContent; el.setAttribute('x', '0'); el.setAttribute('y', '0'); el.setAttribute('visibility', 'hidden');
        it.tx.parentNode.appendChild(el); probes.push({ it: it, el: el });
      });
      C.geo.nums.forEach(function (n) {
        if (!n.width) { try { n.width = n.el.getComputedTextLength(); } catch (e) { n.width = 0; } }
        if (!n.fh) { try { n.fh = parseFloat(g.getComputedStyle(n.el).fontSize) || 11; } catch (e2) { n.fh = 11; } }
        if (!n.textBox) {
          try {
            var b = n.el.getBBox(), x = parseFloat(n.el.getAttribute('x')) || 0, y = parseFloat(n.el.getAttribute('y')) || 0;
            if (b.width > 0 && b.height > 0) n.textBox = [b.x - x, b.y - y, b.x + b.width - x, b.y + b.height - y];
          } catch (e3) {  }
        }
      });
      probes.forEach(function (o) {
        try { var b = o.el.getBBox(); if (b.width > 0 && b.height > 0) o.it.numberBounds = [b.y, b.y + b.height]; } catch (e) {  }
      });
      C.items.forEach(function (it) {
        if (!it.parts || it.tw2 || !it.tw) return;
        var n = (it.text || '').length || 1, k = Math.max(it.parts[0].length, it.parts[1].length) / n;
        it.tw2 = it.tw * k;
      });
      probes.forEach(function (o) { o.el.remove(); });
    }
    function placeNumbers() {
      var placed = [], gap = 8, font = 11;
      C.geo.nums.forEach(function (n) {
        var p = C.projA(C.geo.rNum, n.a); if (!p) return;
        var w = n.width || n.el.textContent.length * font * 0.65, x = p[0], y = p[1], changed = false;
        for (var pass = 0; pass < placed.length + 2; pass++) {
          changed = false;
          for (var j = 0; j < placed.length; j++) {
            var b = placed[j], dx = x - b.x, dy = y - b.y;
            if (Math.abs(dy) >= font + gap || Math.abs(dx) >= (w + b.w) / 2 + gap) continue;
            var near = (w + b.w) / 2 + gap;
            x = b.x + (dx < 0 ? -near : near); changed = true;
          }
          if (!changed) break;
        }
        n.el.setAttribute('x', x.toFixed(1)); n.el.setAttribute('y', y.toFixed(1));
        n.point = [x, y];
        n.layoutWidth = w; n.basePoint = [x, y];
        placed.push({ x: x, y: y, w: w });
      });
    }
    function reproject(moved) { var items = C.items, geo = C.geo, P = C.P;
      C.stats.projections++;
      var i, it, d, gl = document.body.classList.contains('skd-gl'), lite = gl && moved;
      measureText();
      if (!gl) {
        geo.ring.el.setAttribute('d', C.pathOf(geo.ring.sm));
        [geo.ticks, geo.majors].forEach(function (T2) {
          d = '';
          T2.list.forEach(function (t) { var a = C.projA(geo.rBez, t.a), b = C.projA(geo.rBez + (t.major ? P.tick : P.tickMinor), t.a); if (a && b) d += 'M' + a[0].toFixed(1) + ' ' + a[1].toFixed(1) + 'L' + b[0].toFixed(1) + ' ' + b[1].toFixed(1); });
          T2.el.setAttribute('d', d);
        });
      }
      placeNumbers();
      geo.vols.forEach(function (n) { var p = C.projA(geo.rNum + P.num * 1.1, n.a); if (p) { n.el.setAttribute('x', p[0].toFixed(1)); n.el.setAttribute('y', p[1].toFixed(1)); } });
      var s0 = C.projA(geo.rBez + P.tick * 1.3, C.angle(0)), s1 = C.projA(geo.lanes ? (geo.rLo || C.R_IN) + 0.004 : geo.rMain - P.mainGap, C.angle(0));
      geo.startMark.setAttribute('d', s0 && s1 ? 'M' + s0[0].toFixed(1) + ' ' + s0[1].toFixed(1) + 'L' + s1[0].toFixed(1) + ' ' + s1[1].toFixed(1) : '');
      if (!gl && geo.spokes && geo.rLo) {
        d = '';
        geo.spokes.list.forEach(function (a) { var p0 = C.projA(geo.rLo, a), p1 = C.projA(C.R_IN, a); if (p0 && p1) d += 'M' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) + 'L' + p1[0].toFixed(1) + ' ' + p1[1].toFixed(1); });
        geo.spokes.el.setAttribute('d', d);
      }
      geo.dorm.forEach(function (o) { o.el.setAttribute('d', C.pathOf(o.sm)); });
      var mid = C.center();
      for (i = 0; i < items.length; i++) {
        it = items[i];
        if (lite && it.kind === 'quiet') { C.staleHit = true; continue; }
        var Q = C.ptsOf(it.sm), bb = null;
        it.Q = Q;
        if (lite) C.staleHit = true;
        else { d = C.dOfPts(Q); if (!gl && it.el) it.el.setAttribute('d', d); it.hit.setAttribute('d', d); }
        if (it.kind !== 'quiet' && Q.length) {
          bb = [Infinity, Infinity, -Infinity, -Infinity];
          Q.forEach(function (p) { bb[0] = Math.min(bb[0], p[0]); bb[1] = Math.min(bb[1], p[1]); bb[2] = Math.max(bb[2], p[0]); bb[3] = Math.max(bb[3], p[1]); });
        }
        it.bb = bb;
        if (it.dots && !gl) it.dots.forEach(function (o) { var p = o.el && C.projA(it.r, o.a); if (p) { o.el.setAttribute('cx', p[0].toFixed(1)); o.el.setAttribute('cy', p[1].toFixed(1)); } });
        if (it.lp) {
          if (!it.tw) { try { it.tw = it.tx.getComputedTextLength(); } catch (e) { it.tw = 0; } }
          if (!it.fh) { try { it.fh = parseFloat(g.getComputedStyle(it.tx).fontSize) || 11; } catch (e2) { it.fh = 11; } }
          it.B = it.smLab ? C.ptsOf(it.smLab) : Q; it.mid = mid; it.tracks = [];
          it.fit = it.tw > 0 && (it.kind !== 'main' || C.trackFor(it, 0).plen >= Math.min(it.tw, it.tw2 || it.tw) + 18);
        }
      }
      if (!lite) C.staleHit = false;
      if (moved && C.placedOnce) C.followLabels(); else C.placeLabels();
      farFade();
      geo.hos.forEach(function (o) { var to = C.byId && C.byId[o.h.to], p = C.projA(to ? to.r : geo.rMain, o.a); o.el.setAttribute('d', p ? C.knot(p, 4.2) : ''); });
      if (C.cursor != null) C.drawCursor();
    }

    return { reproject: reproject };
  }
  g.CLSkyDiscLayout = { create: create };
})(window);
