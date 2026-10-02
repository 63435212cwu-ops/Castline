/**
 * @role component
 * @owns js/sky/sky-disc-layout.js
 * 投影落盘、刻度回数排布与远侧亮度；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    /* 光层在时，弧 / 珠 / 刻度 / 外环的 SVG 都是透明的（只留字与命中）：不写它们的几何；
       镜头运动中细支（无字）与所有命中路径都不重算，停稳 140 ms 后补一次全量（大书 1400 条路径逐帧重写曾占旋转帧 10%） */
    /* 远侧淡化：盘面斜过去以后，名字按弧中点离镜头的相对远近压淡（最远一侧到 55%），近处照常 */
    function farFade() { var E = C.E, items = C.items;
      if (!E) return;
      var wc = E[15]; if (!(wc > 1e-6)) return;
      for (var i = 0; i < items.length; i++) {
        var it = items[i]; if (!it.tx) continue;
        var am = (it.a0 + it.a1) / 2, w = E[3] * it.r * Math.cos(am) + E[7] * it.r * Math.sin(am) + E[11] * C.zAt(it.r) + wc;
        var fk = C.clamp(((w - wc) / wc - 0.10) / 0.10, 0, 1), fo = (1 - 0.45 * fk).toFixed(2);   /* 相对深度 ≤10%（剧情态默认取景）不动 */
        if (it.fo !== fo) { it.fo = fo; it.tx.setAttribute('fill-opacity', fo); it.tx.setAttribute('stroke-opacity', fo); }
      }
    }
    /* 回数保留在真实刻度附近；重排文字，首尾数字之间留出可读的空隙。 */
    function placeNumbers() {
      var placed = [], gap = 8, font = 11;
      C.geo.nums.forEach(function (n) {
        var p = C.projA(C.geo.rNum, n.a); if (!p) return;
        if (!n.width) { try { n.width = n.el.getComputedTextLength(); } catch (e) { n.width = 0; } }
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
        placed.push({ x: x, y: y, w: w });
      });
    }
    function reproject(moved) { var items = C.items, geo = C.geo, P = C.P;
      C.stats.projections++;
      var i, it, d, gl = document.body.classList.contains('skd-gl'), lite = gl && moved;
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
      var s0 = C.projA(geo.rBez + P.tick * 1.3, C.angle(0)), s1 = C.projA(geo.lanes ? C.R_IN + 0.004 : geo.rMain - P.mainGap, C.angle(0));   /* 起点子午线止于 1.10R：不伸进团名带 */
      geo.startMark.setAttribute('d', s0 && s1 ? 'M' + s0[0].toFixed(1) + ' ' + s0[1].toFixed(1) + 'L' + s1[0].toFixed(1) + ' ' + s1[1].toFixed(1) : '');
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
          it.B = Q; it.mid = mid; it.tracks = [];   /* 顺时针（a0→a1）屏幕折线；字的朝向在 setTrack 里按落点定 */
          /* 主线段名只写在自己段外侧，段太短就不写；支线名还有车道端点两条退路，只要量得出字宽就参与避让 */
          it.fit = it.tw > 0 && (it.kind !== 'main' || C.trackFor(it, 0).plen >= it.tw + 18);
        }
      }
      /* 镜头在动时名字只跟着字轨走、不重新避让（否则推拉过程中名字一闪一灭）；停稳 140ms 后再统一避让一次 */
      if (!lite) C.staleHit = false;
      if (moved && C.placedOnce) C.followLabels(); else C.placeLabels();
      farFade();
      geo.hos.forEach(function (o) { var p = C.projA(geo.rMain, o.a); o.el.setAttribute('d', p ? C.knot(p, 4.2) : ''); });
      if (C.cursor != null) C.drawCursor();
    }

    return { reproject: reproject };
  }
  g.CLSkyDiscLayout = { create: create };
})(window);
