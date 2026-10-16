/**
 * @role component
 * @owns js/sky/sky-disc-labels.js
 * 标签优先级、候选避让与镜头运动时跟随；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    var TRIES_MAIN = [0.5, 0.32, 0.68, 0.2, 0.8, 0.14, 0.86], TRIES_NAMED = [0.5, 0.38, 0.62, 0.26, 0.74, 0.15, 0.85];
    function numberBox(n, p) {
      var b = n.textBox || [-n.layoutWidth / 2, -n.fh * C.INK, n.layoutWidth / 2, n.fh * C.INK];
      return [p[0] + b[0], p[1] + b[1], p[0] + b[2], p[1] + b[3]];
    }
    function touchesNumber(fp, it, box) {
      var gap = C.LAB_PAD, bounds = it.numberBounds || [-it.fh * C.INK, it.fh * C.INK];
      if (fp.inkBox) {
        var old = fp.inkBox, y = (old[1] + old[3]) / 2, b = [old[0], y + bounds[0], old[2], y + bounds[1]];
        var dx = Math.max(box[0] - b[2], b[0] - box[2], 0), dy = Math.max(box[1] - b[3], b[1] - box[3], 0);
        return dx * dx + dy * dy < gap * gap;
      }
      var pad = Math.max(Math.abs(bounds[0]), Math.abs(bounds[1])) + gap;
      for (var j = 0; j < fp.length; j++) {
        var p = fp[j], px = Math.max(box[0] - p[0], p[0] - box[2], 0), py = Math.max(box[1] - p[1], p[1] - box[3], 0);
        if (px * px + py * py < pad * pad) return true;
      }
      return false;
    }
    function numberClash(fp, it) {
      return (C.geo && C.geo.nums || []).some(function (n) { return n.basePoint && touchesNumber(fp, it, numberBox(n, n.basePoint)); });
    }
    function clearNumbers() {
      if (!C.geo || !C.geo.nums) return;
      C.geo.nums.forEach(function (n) {
        if (!n.basePoint) return;
        n.point = n.basePoint.slice();
        n.el.setAttribute('x', n.point[0].toFixed(1)); n.el.setAttribute('y', n.point[1].toFixed(1));
      });
      var labels = C.items.filter(function (it) { return it.shown && it.lp; }).map(function (it) {
        if (it.two && C.footprint2) { var fp2 = C.footprint2(it, it.side || 0, it.f); if (fp2) return { fp: fp2, it: it }; }
        var T = C.trackFor(it, it.side || 0), f = it.f;
        if (!T) { T = C.trackFor(it, 0); f = 0.5; }
        return { fp: T ? C.footprint(it, T, f) : null, it: it };
      }).filter(function (o) { return !!o.fp; });
      function titleClash(box) { return labels.some(function (o) { return touchesNumber(o.fp, o.it, box); }); }
      C.geo.nums.forEach(function (n) {
        if (!n.point || !titleClash(numberBox(n, n.point))) return;
        var a = C.projA(C.geo.rNum, n.a), b = C.projA(C.geo.rNum + C.P.num, n.a); if (!a || !b) return;
        var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy); if (len < 1e-6) return;
        for (var d = 2; d <= n.fh * 2; d += 2) {
          var p = [n.basePoint[0] + dx / len * d, n.basePoint[1] + dy / len * d], box = numberBox(n, p);
          if (box[0] < C.LAB_PAD || box[2] > C.Wv - C.LAB_PAD || box[1] < C.LAB_PAD || box[3] > C.Hv - C.LAB_PAD || titleClash(box)) continue;
          if (C.geo.nums.some(function (q) { return q !== n && q.point && Math.abs(p[1] - q.point[1]) < 19 && Math.abs(p[0] - q.point[0]) < (n.layoutWidth + q.layoutWidth) / 2 + 8; })) continue;
          n.point = p; n.el.setAttribute('x', p[0].toFixed(1)); n.el.setAttribute('y', p[1].toFixed(1)); break;
        }
      });
      clearVolumes(titleClash);
      if (C.cursor != null) C.drawCursor();
    }
    function boxHit(a, b, gap) { return a[0] < b[2] + gap && b[0] < a[2] + gap && a[1] < b[3] + gap && b[1] < a[3] + gap; }
    function clearVolumes(titleClash) {
      var V = C.geo && C.geo.vols; if (!V || !V.length) return;
      var gap = 8, numBoxes = C.geo.nums.filter(function (n) { return n.point; }).map(function (n) { return numberBox(n, n.point); }), placed = [];
      V.forEach(function (v) {
        var base = C.projA(C.geo.rNum + C.P.num * 1.1, v.a); if (!base) return;
        if (!v.fh) { try { v.fh = parseFloat(g.getComputedStyle(v.el).fontSize) || 11; } catch (e) { v.fh = 11; } }
        if (!v.textBox) {
          try {
            v.el.setAttribute('x', base[0].toFixed(1)); v.el.setAttribute('y', base[1].toFixed(1));
            var bb = v.el.getBBox(); if (bb.width > 0 && bb.height > 0) v.textBox = [bb.x - base[0], bb.y - base[1], bb.x + bb.width - base[0], bb.y + bb.height - base[1]];
          } catch (e2) {  }
        }
        var tb = v.textBox || [-v.fh * 1.2, -v.fh * 0.6, v.fh * 1.2, v.fh * 0.6];
        function boxAt(p) { return [p[0] + tb[0], p[1] + tb[1], p[0] + tb[2], p[1] + tb[3]]; }
        function free(p) {
          var b = boxAt(p);
          if (b[0] < C.LAB_PAD || b[2] > C.Wv - C.LAB_PAD || b[1] < C.LAB_PAD || b[3] > C.Hv - C.LAB_PAD) return false;
          if (numBoxes.some(function (q) { return boxHit(b, q, gap); }) || placed.some(function (q) { return boxHit(b, q, gap); })) return false;
          return !titleClash(b);
        }
        var cands = [base], k, p, out = C.projA(C.geo.rNum + C.P.num * 2.1, v.a);
        if (out) {
          var ox = out[0] - base[0], oy = out[1] - base[1], ol = Math.hypot(ox, oy);
          if (ol > 1e-6) for (k = 2; k <= v.fh * 2.4; k += 2) cands.push([base[0] + ox / ol * k, base[1] + oy / ol * k]);
        }
        [0.012, 0.024, 0.036, 0.05].forEach(function (da) { [1, -1].forEach(function (s) { p = C.projA(C.geo.rNum + C.P.num * 1.1, v.a + s * da); if (p) cands.push(p); }); });
        var hit = null;
        for (k = 0; k < cands.length && !hit; k++) if (free(cands[k])) hit = cands[k];
        var at = hit || base;
        v.el.setAttribute('x', at[0].toFixed(1)); v.el.setAttribute('y', at[1].toFixed(1));
        v.el.classList.toggle('is-masked', !hit);
        if (hit) placed.push(boxAt(hit));
      });
    }
    function placeLabels() {
      C.placedOnce = true;
      if (C.growT0 >= 0) C.svg.style.setProperty('--sd-name-delay', Math.max(0, Math.round(2000 - (C.now() - C.growT0))) + 'ms');
      var active = C.focusId || C.hoverId;
      var list = C.items.filter(function (it) { return it.lp && it.fit; }).sort(function (a, b) { return (a.id === active ? -1 : 0) - (b.id === active ? -1 : 0) || (a.kind === 'main' ? -1 : 0) - (b.kind === 'main' ? -1 : 0) || (a.line.rank || 0) - (b.line.rank || 0); });
      var placed = [];
      C.items.forEach(function (it) { if (it.tx && !it.fit) { it.tx.classList.remove('is-fit'); it.shown = false; setTrack(it, it.tracks && it.tracks[0], 0.5); } });
      list.forEach(function (it) {
        var ok = null, fallback = null, sides = it.kind === 'main' ? [0] : [0, 2, 3, 1];
        var modes = it.parts && it.tw2 && C.footprint2 ? [false, true] : [false];
        for (var m = 0; m < modes.length && !ok && !fallback; m++) {
          var two = modes[m];
          for (var s = 0; s < sides.length && !ok; s++) {
            var T = C.trackFor(it, sides[s], two ? 1 : 0);
            if (!T) continue;
            var tries = it.kind === 'main' ? TRIES_MAIN : sides[s] >= 2 ? [T.fNear] : TRIES_NAMED;
            for (var k = 0; k < tries.length && !ok; k++) {
              var fp = two ? C.footprint2(it, sides[s], tries[k]) : C.footprint(it, T, tries[k]); if (!fp) continue;
              if (placed.some(function (q) { return C.clash(fp, q); })) continue;
              if (C.arcClash(fp, it)) continue;
              var candidate = { f: tries[k], fp: fp, T: T, side: sides[s], two: two };
              if (numberClash(fp, it)) { if (!fallback) fallback = candidate; continue; }
              ok = candidate;
            }
          }
        }
        ok = ok || fallback;
        it.shown = !!ok; it.side = ok ? ok.side : 0; it.f = ok ? ok.f : 0.5; it.two = !!(ok && ok.two);
        if (it.tx && it.tx.classList) {
          it.tx.classList.toggle('is-fit', !!ok);
          it.tx.classList.toggle('is-outer', !!ok && ok.side === 1);
          it.tx.classList.toggle('is-lane', !!ok && ok.side >= 2);
        }
        if (ok) { placed.push(ok.fp); if (ok.two) setTwo(it, ok.side, ok.f); else setTrack(it, ok.T, ok.f); } else setTrack(it, it.tracks[0], 0.5);
      });
      clearNumbers();
    }
    function followLabels() {
      C.items.forEach(function (it) {
        if (!it.lp || !it.tracks) return;
        if (it.shown && it.two && setTwo(it, it.side || 0, it.f)) return;
        var T = it.shown ? C.trackFor(it, it.side || 0) : null; if (T) setTrack(it, T, it.f); else setTrack(it, C.trackFor(it, 0), 0.5);
      });
      clearNumbers();
    }
    function rev(T) { return T.rv || (T.rv = C.track(T.P.slice().reverse())); }
    function writeLine(lp, tp, T, f, text, key) {
      if (T.d == null) T.d = C.dOfPts(T.P);
      if (lp[key] !== T.d) { lp.setAttribute('d', T.d); lp[key] = T.d; }
      var so = (f * 100).toFixed(1) + '%'; if (tp.getAttribute('startOffset') !== so) tp.setAttribute('startOffset', so);
      if (text != null && tp.textContent !== text) tp.textContent = text;
    }
    function setTwo(it, side, f) {
      var S = C.shape2 && C.shape2(it, side, f); if (!S || !it.tp2) return false;
      var A = S.lines[0], B = S.lines[1];
      if (!S.horizontal) {
        var Tn = A[0], tw = it.tw2 || it.tw, d = Tn.plen * f, half = Math.max(6, tw / 2), a = C.at(Tn, d - half), b = C.at(Tn, d + half), flip = !!it.flip;
        if (a && b) { var vx = b[0] - a[0], L = Math.hypot(vx, b[1] - a[1]) || 1; if (vx < -0.17 * L) flip = true; else if (vx > 0.17 * L) flip = false; }
        it.flip = flip;
        var ff = flip ? 1 - f : f, n = flip ? rev(Tn) : Tn, o = flip ? rev(B[0]) : B[0];
        var pn = C.at(n, n.plen * ff), po = C.at(o, o.plen * ff), ra = C.at(n, n.plen * ff - half), rb = C.at(n, n.plen * ff + half);
        var nearUp = pn && po && ra && rb ? (pn[0] - po[0]) * (rb[1] - ra[1]) + (pn[1] - po[1]) * (-(rb[0] - ra[0])) > 0 : false;
        A = nearUp ? [n, ff] : [o, ff]; B = nearUp ? [o, ff] : [n, ff];
      }
      writeLine(it.lp, it.tp, A[0], A[1], it.parts[0], 'lpD');
      writeLine(it.lp2, it.tp2, B[0], B[1], it.parts[1], 'lpD2');
      if (it.tx && it.tx.classList) {
        it.tx.classList.toggle('is-horizontal', !!S.horizontal);
        it.tx.classList.toggle('is-tangent', !S.horizontal);
        it.tx.classList.toggle('is-outer', it.side === 1);
        it.tx.classList.toggle('is-lane', it.side >= 2);
        it.tx.classList.add('is-two');
      }
      return true;
    }
    function setTrack(it, T, f) {
      if (!T) return;
      var up = C.uprightTrack(it, T, f); T = up.T; f = up.f;
      var d = T.plen * f, half = Math.max(6, (it.tw || 24) / 2), a = C.at(T, d - half), b = C.at(T, d + half), flip = !!it.flip;
      if (a && b) { var vx = b[0] - a[0], L = Math.hypot(vx, b[1] - a[1]) || 1; if (vx < -0.17 * L) flip = true; else if (vx > 0.17 * L) flip = false; }
      it.flip = flip;
      if (flip) { T = T.rv || (T.rv = C.track(T.P.slice().reverse())); f = 1 - f; }
      if (T.d == null) T.d = C.dOfPts(T.P);
      if (it.lpD !== T.d) { it.lp.setAttribute('d', T.d); it.lpD = T.d; }
      var so = (f * 100).toFixed(1) + '%'; if (it.tp.getAttribute('startOffset') !== so) it.tp.setAttribute('startOffset', so);
      if (it.tp2) { if (it.tp.textContent !== it.text) it.tp.textContent = it.text; if (it.tp2.textContent) it.tp2.textContent = ''; }
      if (it.tx && it.tx.classList) {
        it.tx.classList.remove('is-two');
        it.tx.classList.toggle('is-horizontal', !!up.horizontal);
        it.tx.classList.toggle('is-tangent', !up.horizontal);
        it.tx.classList.toggle('is-outer', it.side === 1);
        it.tx.classList.toggle('is-lane', it.side >= 2);
      }
    }
    return { placeLabels: placeLabels, followLabels: followLabels, setTrack: setTrack };
  }
  g.CLSkyDiscLabels = { create: create };
})(window);
