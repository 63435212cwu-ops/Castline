/**
 * @role component
 * @owns js/sky/sky-disc-labels.js
 * 标签优先级、候选避让与镜头运动时跟随；仅由星盘状态与帧钩子驱动。
 */
(function (g) {
  'use strict';
  function create(C) {
    var TRIES_MAIN = [0.5, 0.32, 0.68, 0.2, 0.8], TRIES_NAMED = [0.5, 0.38, 0.62, 0.26, 0.74, 0.15, 0.85];
    /* 名字最后出现：不管避让在第几毫秒完成，名字都在唤醒后 ≥2s 才淡入（生长动画期间） */
    function placeLabels() {
      C.placedOnce = true;
      if (C.growT0 >= 0) C.svg.style.setProperty('--sd-name-delay', Math.max(0, Math.round(2000 - (C.now() - C.growT0))) + 'ms');
      var active = C.focusId || C.hoverId;
      var list = C.items.filter(function (it) { return it.lp && it.fit; }).sort(function (a, b) { return (a.id === active ? -1 : 0) - (b.id === active ? -1 : 0) || (a.kind === 'main' ? -1 : 0) - (b.kind === 'main' ? -1 : 0) || (a.line.rank || 0) - (b.line.rank || 0); });
      var placed = [];
      C.items.forEach(function (it) { if (it.tx && !it.fit) { it.tx.classList.remove('is-fit'); it.shown = false; setTrack(it, it.tracks && it.tracks[0], 0.5); } });
      list.forEach(function (it) {
        var ok = null, sides = it.kind === 'main' ? [0] : [0, 2, 3, 1];
        for (var s = 0; s < sides.length && !ok; s++) {
          var T = C.trackFor(it, sides[s]);
          if (!T) continue;
          var tries = it.kind === 'main' ? TRIES_MAIN : sides[s] >= 2 ? [T.fNear] : TRIES_NAMED;
          for (var k = 0; k < tries.length && !ok; k++) {
            var fp = C.footprint(it, T, tries[k]); if (!fp) continue;
            if (placed.some(function (q) { return C.clash(fp, q); })) continue;
            if (C.arcClash(fp, it)) continue;
            ok = { f: tries[k], fp: fp, T: T, side: sides[s] };
          }
        }
        it.shown = !!ok; it.side = ok ? ok.side : 0; it.f = ok ? ok.f : 0.5;
        it.tx.classList.toggle('is-fit', !!ok);
        it.tx.classList.toggle('is-outer', !!ok && ok.side === 1);
        it.tx.classList.toggle('is-lane', !!ok && ok.side >= 2);
        if (ok) { placed.push(ok.fp); setTrack(it, ok.T, ok.f); } else setTrack(it, it.tracks[0], 0.5);
      });
    }
    function followLabels() {
      C.items.forEach(function (it) { if (!it.lp || !it.tracks) return; var T = it.shown ? C.trackFor(it, it.side || 0) : null; if (T) setTrack(it, T, it.f); else setTrack(it, C.trackFor(it, 0), 0.5); });
    }
    /* 正立：按名字落点处字轨在屏幕上的实际走向定——字序从右往左（倒字）就把字轨反过来写。
     * 盘面正视时等价于「下半周翻成字头朝内」；斜到 70°、再绕着转时也不会出倒字。近乎竖直（±10°）时保持上一次的朝向，不来回翻 */
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
    }
    return { placeLabels: placeLabels, followLabels: followLabels, setTrack: setTrack };
  }
  g.CLSkyDiscLabels = { create: create };
})(window);
