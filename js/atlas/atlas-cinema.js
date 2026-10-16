(function (g) {
  'use strict';
  var d = g.document, root = d && d.documentElement, stage = null, layer = null;
  var raf = 0, px = .5, py = .44, flight = 0, reduced = false, low = false, clean = [], cutTimer = 0;
  function media() { try { return !!(g.matchMedia && g.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; } }
  function nativeSky() { return !!(d.body && d.body.classList.contains('sky-shell') && d.body.classList.contains('skd-gl')); }
  function quiet() { return media() || !!(d.body && (d.body.classList.contains('skylab-still') || d.body.classList.contains('atlas-motion-quiet'))); }
  function vars() {
    reduced = quiet(); low = !!(d.body && d.body.getAttribute('data-tier') === 'low');
    if (reduced || low) { px = .5; py = .44; flight = 0; }
    var t = nativeSky() && layer ? null : layer || root, dp = Math.min(1, Math.abs(px - .5) + Math.abs(py - .44)).toFixed(3), gh = layer ? d.querySelectorAll('.cl-gem-host') : [];
    if (t) {
      t.style.setProperty('--cinema-x', (px * 100).toFixed(2) + '%');
      t.style.setProperty('--cinema-y', (py * 100).toFixed(2) + '%');
      t.style.setProperty('--cinema-depth', dp);
      t.style.setProperty('--cinema-flight', flight.toFixed(3));
    }
    for (var i = 0; i < gh.length; i++) gh[i].style.setProperty('--cinema-depth', dp);
  }
  var grade = { sat: 1, con: 1, bri: 1, tSat: 1, tCon: 1, tBri: 1, tau: .16, raf: 0, pass: null, passFrom: 0 };
  function gradeFor(b) {
    if (b && b.classList.contains('atlas-workspace')) {
      var v = b.getAttribute('data-atlas-view');
      if (v === 'gem') return [1.18, 1.05, .98];
      if (v === 'domains') return [1.14, 1.06, .96];
      if (v) return [1.1, 1.04, .97];
    }
    if (b && b.classList.contains('cinema-flight')) return [1.12, 1.04, 1.01];
    return [1.16, 1.08, .94];
  }
  function gradePass() {
    if (grade.pass && grade.passFrom > 0) return grade.pass;
    grade.passFrom++;
    try {
      var app = g.CLApp, S = app && app.scene && app.scene();
      var C = S && S.core && S.core().getComposer && S.core().getComposer();
      var passes = C && C.passes || [];
      grade.pass = null;
      for (var i = 0; i < passes.length; i++) {
        var u = passes[i] && passes[i].uniforms;
        if (u && 'uSat' in u && 'uContrast' in u && 'uBright' in u) { grade.pass = passes[i]; break; }
      }
    } catch (e) { grade.pass = null; }
    return grade.pass;
  }
  function gradeWrite(s, c, b) {
    var p = gradePass(); if (!p) return;
    p.uniforms.uSat.value = s; p.uniforms.uContrast.value = c; p.uniforms.uBright.value = b;
  }
  function gradeFrame(t) {
    grade.raf = 0;
    var dt = Math.min(.1, Math.max(.008, (t - (grade.t || t - 16)) / 1000)); grade.t = t;
    var k = 1 - Math.exp(-dt / grade.tau);
    grade.sat += (grade.tSat - grade.sat) * k;
    grade.con += (grade.tCon - grade.con) * k;
    grade.bri += (grade.tBri - grade.bri) * k;
    var done = Math.abs(grade.tSat - grade.sat) + Math.abs(grade.tCon - grade.con) + Math.abs(grade.tBri - grade.bri) < .0005;
    if (done) { grade.sat = grade.tSat; grade.con = grade.tCon; grade.bri = grade.tBri; }
    gradeWrite(grade.sat, grade.con, grade.bri);
    if (!done) grade.raf = g.requestAnimationFrame(gradeFrame);
  }
  function syncGrade() {
    var b = d.body;
    var tgt = gradeFor(b);
    grade.tSat = tgt[0]; grade.tCon = tgt[1]; grade.tBri = tgt[2];
    grade.tau = (b && b.classList.contains('cinema-flight')) ? .26 : .16;
    if (quiet()) { grade.sat = grade.tSat; grade.con = grade.tCon; grade.bri = grade.tBri; gradeWrite(grade.sat, grade.con, grade.bri); return; }
    if (!grade.raf) { grade.t = 0; grade.raf = g.requestAnimationFrame(gradeFrame); }
  }

  function mount() {
    if (!d || !d.body || layer) return layer;
    stage = d.getElementById('stage');
    layer = d.createElement('div'); layer.className = 'cinema-depth'; layer.setAttribute('aria-hidden', 'true');
    ['grain', 'bloom', 'iris', 'sweep', 'gate', 'runes', 'meteor', 'pulse'].forEach(function (name) {
      var e = d.createElement('i'); e.className = 'cinema-depth__' + name; layer.appendChild(e);
    });
    (stage || d.body).appendChild(layer);
    vars();
    function occult(cls, duration) {
      if (!d.body || reduced || low) return;
      d.body.classList.remove(cls);
      g.requestAnimationFrame(function () { if (d.body) d.body.classList.add(cls); });
      g.setTimeout(function () { if (d.body) d.body.classList.remove(cls); }, duration);
    }
    function seedMeteor() {
      var mt = layer || root;
      mt.style.setProperty('--cinema-meteor-x', (8 + Math.random() * 62).toFixed(2) + '%');
      mt.style.setProperty('--cinema-meteor-y', (17 + Math.random() * 55).toFixed(2) + '%');
      mt.style.setProperty('--cinema-meteor-angle', (-34 + Math.random() * 28).toFixed(2) + 'deg');
    }
    function move(e) {
      if (nativeSky() || reduced || low || !stage) return;
      px = Math.max(0, Math.min(1, e.clientX / Math.max(1, g.innerWidth)));
      py = Math.max(0, Math.min(1, e.clientY / Math.max(1, g.innerHeight)));
      if (!raf) raf = g.requestAnimationFrame(function () { raf = 0; vars(); });
    }
    function down(e) {
      if (nativeSky() || reduced || low || !stage || e.pointerType === 'mouse' && e.button > 0) return;
      flight = Math.min(1, flight + .58); vars();
      if (d.body) d.body.classList.add('cinema-flight');
      occult('cinema-pulse', 920);
    }
    function up() {
      flight = .22; vars();
      if (d.body) d.body.classList.remove('cinema-flight');
      g.setTimeout(function () { flight = 0; vars(); }, reduced ? 0 : 720);
    }
    function cut(e) {
      if (nativeSky() || reduced || low || !d.body) return;
      if (cutTimer) g.clearTimeout(cutTimer);
      d.body.classList.remove('cinema-cut', 'cinema-gate', 'cinema-meteor');
      seedMeteor();
      g.requestAnimationFrame(function () {
        if (!d.body) return;
        d.body.classList.add('cinema-cut', 'cinema-gate', 'cinema-meteor');
      });
      cutTimer = g.setTimeout(function () { if (d.body) d.body.classList.remove('cinema-cut'); cutTimer = 0; }, 1020);
      g.setTimeout(function () { if (d.body) d.body.classList.remove('cinema-gate', 'cinema-meteor'); }, 1880);
      var v = e && e.detail && e.detail.view;
      if (v) d.body.setAttribute('data-cinema-lens', v);
    }
    d.addEventListener('pointermove', move, { passive: true }); clean.push(function () { d.removeEventListener('pointermove', move); });
    d.addEventListener('pointerdown', down, { passive: true, capture: true }); clean.push(function () { d.removeEventListener('pointerdown', down, true); });
    d.addEventListener('pointerup', up, { passive: true, capture: true }); d.addEventListener('pointercancel', up, { passive: true, capture: true });
    clean.push(function () { d.removeEventListener('pointerup', up, true); d.removeEventListener('pointercancel', up, true); });
    d.addEventListener('cl:atlas-view', cut, { passive: true }); clean.push(function () { d.removeEventListener('cl:atlas-view', cut); });
    g.addEventListener('resize', vars, { passive: true }); clean.push(function () { g.removeEventListener('resize', vars); });
    d.addEventListener('visibilitychange', function () { if (d.hidden) { flight = 0; if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0; vars(); } });
    if (g.MutationObserver) {
      var mo = new g.MutationObserver(function () { vars(); syncGrade(); });
      mo.observe(d.body, { attributes: true, attributeFilter: ['class', 'data-tier', 'data-atlas-view'] });
      clean.push(function () { mo.disconnect(); });
    }
    syncGrade();
    return layer;
  }
  function dispose() {
    while (clean.length) { try { clean.pop()(); } catch (e) {} }
    if (cutTimer) g.clearTimeout(cutTimer); cutTimer = 0;
    if (raf && g.cancelAnimationFrame) g.cancelAnimationFrame(raf); raf = 0;
    if (grade.raf && g.cancelAnimationFrame) g.cancelAnimationFrame(grade.raf); grade.raf = 0;
    grade.sat = grade.con = grade.bri = grade.tSat = grade.tCon = grade.tBri = 1;
    gradeWrite(1, 1, 1);
    if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
    layer = stage = null; flight = 0;
  }
  g.CLAtlasCinema = { mount: mount, dispose: dispose, stats: function () { return { mounted: layer ? 1 : 0, reduced: reduced ? 1 : 0, low: low ? 1 : 0, flight: flight, grade: [grade.sat, grade.con, grade.bri], gradeTarget: [grade.tSat, grade.tCon, grade.tBri] }; } };
  if (d && d.readyState === 'loading') d.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
})(window);
