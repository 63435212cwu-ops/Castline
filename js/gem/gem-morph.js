(function () {
  'use strict';
  var MAX_DT = 50, DEF_DT = 16;

  function ease(t) { return 1 - Math.pow(1 - t, 3); }

  function create(opts) {
    var draw = (opts && opts.draw) || function () {};
    var durFn = (opts && opts.dur) || function () { return 0; };
    var faces = [], anim = null, raf = 0, lastT = 0;

    function advance(ms) {
      if (!anim) return;
      anim.t += ms;
      var D = durFn(), k = D > 0 ? ease(Math.min(1, anim.t / D)) : 1, i, j, F, a, b;
      for (i = 0; i < faces.length; i++) {
        F = faces[i];
        if (!F.from || !F.target || !F.cur) continue;
        for (j = 0; j < 8; j++) {
          a = F.from[j]; b = F.target[j];
          F.cur[j] = (b == null) ? null : (a == null ? b : a + (b - a) * k);
        }
        draw(F);
      }
      if (anim.t >= D) cancel();
    }
    function tick(t) {
      raf = 0;
      var dt = lastT ? Math.min(MAX_DT, t - lastT) : DEF_DT; lastT = t;
      advance(dt);
      if (anim) raf = requestAnimationFrame(tick); else lastT = 0;
    }
    function start(fs) {
      var i, j, F, changed = false;
      cancel();
      faces = fs || [];
      for (i = 0; i < faces.length; i++) {
        F = faces[i];
        if (!F.cur || !F.target) continue;
        var snapped = false;
        for (j = 0; j < 8; j++) {
          if (F.cur[j] === F.target[j]) continue;
          if (F.cur[j] == null || F.target[j] == null) { F.cur[j] = F.target[j]; snapped = true; }
          else changed = true;
        }
        F.from = F.cur.slice(0);
        if (snapped) draw(F);
      }
      if (!changed) { faces = []; return; }
      anim = { t: 0 };
      if (!raf) raf = requestAnimationFrame(tick);
    }
    function cancel() {
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      anim = null; lastT = 0; faces = [];
    }
    function active() { return !!anim; }
    return { start: start, advance: advance, active: active, cancel: cancel };
  }

  window.CLGemMorph = { name: 'gem-morph', version: 'v80', ease: ease, create: create };
})();
