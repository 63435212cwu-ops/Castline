/**
 * @role shell-player
 * @owns js/sky/sky-shell-player.js
 * 章节游标、播放计时器与当前章节字幕。状态由 sky-shell 持有，X 是显式闭包桥；不创建帧循环。
 */
(function (g) {
  'use strict';
  function create(X) {
  function clearCursor() { if (!X.disc) return; X.disc.setCursor(null); if (X.el.skyScrub) X.el.skyScrub.value = '0'; caption(null); if (g.CLSkyDeep) CLSkyDeep.setCursor(null); if (X.deck) X.deck.setCursor(null); if (!X.hoverInfo && !X.selInfo && !X.deckInfo) X.light(null); }
  function caption(c) {
    if (!X.el.skyCaption) return;
    if (c == null || !X.M) { X.el.skyCaption.textContent = ''; return; }
    var ch = X.M.chapters[c], evs = (X.M.chapterEvents[c] || []).map(function (i) { return X.G.events[i]; }), key = evs.filter(function (e) { return /转折|高燃|抉择|冲突/.test(e.kind || ''); })[0] || evs[0];
    X.el.skyCaption.innerHTML = '<b>' + (X.M.axis && X.M.axis.mode === 'seq' ? X.esc(String(ch.name || '').slice(0, 14)) : '第 ' + ch.no + ' ' + X.unit()) + '</b>' + (ch.short ? '<span>' + X.esc(ch.short) + '</span>' : '') + (key ? '<i>' + X.esc(key.title || key.summary || '') + '</i>' : '') + '<em>' + (X.M.chapterCast[c] || []).length + ' 人在场</em>';
  }
  function seek(c) {
    if (!X.M || !X.disc) return;
    if (c == null) { stopPlay(); clearCursor(); return; }
    c = Math.max(0, Math.min(X.M.nCh - 1, c | 0));
    X.disc.setCursor(c); X.el.skyScrub.value = String(c); caption(c);
    if (g.CLSkyDeep) CLSkyDeep.setCursor(c);
    if (X.deck) X.deck.setCursor(c);
    if (!X.hoverInfo && !X.selInfo && !X.deckInfo) X.light(X.M.chapterCast[c]);
  }
  function startTimer() { X.playT = setInterval(function () { if (X.doc.hidden) { stopPlay(); return; } var c = X.disc.cursor(); if (c == null) c = -1; if (c >= X.M.nCh - 1) { stopPlay(); return; } seek(c + 1); }, 900 / X.speed); }
  function stopTimer() { if (X.playT) clearInterval(X.playT); X.playT = null; }
  function togglePlay() { if (X.playing) stopPlay(); else { if (!X.plot) X.setPlot(true); X.playing = true; X.el.skyPlay.innerHTML = X.GLYPH.pause; X.el.skyPlay.setAttribute('aria-pressed', 'true'); var c = X.disc.cursor(); if (c == null || c >= X.M.nCh - 1) seek(0); startTimer(); } }
  function stopPlay() { X.playing = false; stopTimer(); if (X.el.skyPlay) { X.el.skyPlay.innerHTML = X.GLYPH.play; X.el.skyPlay.setAttribute('aria-pressed', 'false'); } }
    return {
      clearCursor: clearCursor,
      caption: caption,
      seek: seek,
      startTimer: startTimer,
      stopTimer: stopTimer,
      togglePlay: togglePlay,
      stopPlay: stopPlay
    };
  }
  g.CLSkyShellPlayer = { create: create };
})(window);
