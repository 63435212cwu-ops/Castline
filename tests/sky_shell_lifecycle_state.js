/* Actual screen hit targets and actual chapter/line casts; never seed private state. */
(function () {
  'use strict';
  function equal(a, b) { return JSON.stringify(Array.from(new Set(a || [])).sort()) === JSON.stringify(Array.from(new Set(b || [])).sort()); }
  function choices() {
    var M = CLSky.model(), D = CLSky.disc(), all = M.mains.concat(M.lines), result = [];
    all.forEach(function (l) {
      var info = D.lineInfo(String(l.id)); if (!info || !info.cast || !info.cast.length) return;
      for (var c = 0; c < M.nCh; c++) { var want = M.chapterCast[c] || []; if (want.length && !equal(want, info.cast.slice(0, 14))) { result.push({ id: String(l.id), chapter: c, want: want.slice(), old: info.cast.slice(0, 14) }); break; } }
    });
    return result;
  }
  function line() {
    var D = CLSky.disc(), list = choices();
    for (var choice of list) {
      var p = Array.from(D.el.querySelectorAll('.sd-hit')).filter(function (e) { return e.getAttribute('data-id') === choice.id; })[0];
      if (!p || !p.getTotalLength || !p.getScreenCTM()) continue;
      for (var k = 1; k < 24; k++) {
        var q = p.getPointAtLength(p.getTotalLength() * k / 24), screen = new DOMPoint(q.x, q.y).matrixTransform(p.getScreenCTM());
        var target = document.elementFromPoint(screen.x, screen.y);
        if (screen.x > 20 && screen.x < innerWidth - 20 && screen.y > 70 && screen.y < innerHeight - 100 && target && target.closest('.sd-hit') && D.pickLine(screen.x, screen.y) === choice.id) return Object.assign(choice, { x: screen.x, y: screen.y });
      }
    }
    throw new Error('no real clickable plot line with a differing chapter cast');
  }
  function card() {
    var list = choices(), bars = document.querySelectorAll('.skd-deck:not([hidden]) .skd-card__bar');
    for (var e of bars) {
      var article = e.closest('[data-key]'), id = article && article.getAttribute('data-key').slice(2), choice = list.filter(function (x) { return x.id === id; })[0];
      if (!choice) continue;
      var b = e.getBoundingClientRect();
      for (var ix of [.2, .5, .8]) for (var iy of [.12, .3, .6]) {
        var x = b.left + b.width * ix, y = b.top + b.height * iy, hit = document.elementFromPoint(x, y);
        if (x > 0 && y > 70 && x < innerWidth && y < innerHeight - 100 && hit && hit.closest('.skd-card__bar') === e) return Object.assign(choice, { x: x, y: y, key: article.getAttribute('data-key') });
      }
    }
    throw new Error('no pointer-reachable real deck card with a differing chapter cast');
  }
  function state() {
    var R = __shellRegression, S = CLApp.scene(), D = CLSky.disc(), deck = CLSky.deck();
    return { plot: CLSky.plot(), mode: CLSky.state().mode, cursor: D.cursor(), focused: D.focused(), hover: D.hover(),
      selected: R.ctx.selInfo && R.ctx.selInfo.id, cardHover: R.ctx.deckInfo && R.ctx.deckInfo.id, arcHover: R.ctx.hoverInfo && R.ctx.hoverInfo.id,
      deck: deck && deck.stats(), search: S.searchNames(), caption: document.getElementById('skyCaption').textContent };
  }
  window.__shellStateCase = { line: line, card: card, state: state, equal: equal }; return true;
})()
