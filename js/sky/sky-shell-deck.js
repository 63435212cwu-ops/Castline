/**
 * @role shell-deck
 * @owns js/sky/sky-shell-deck.js
 * 模型到剧情卡片叠的投影、事件摘要与选中联动。状态由 sky-shell 持有，X 是显式闭包桥；不创建帧循环。
 */
(function (g) {
  'use strict';
  var DECK_KEY = /转折|高燃|抉择|冲突|高潮|揭秘/;
  function create(X) {
  function deckOn() { return !!(X.deck && X.plot && X.mode !== 'compass' && !X.narrow()); }
  function deckRect() {
    var top = X.hud ? X.hud.querySelector('.sky-top').getBoundingClientRect().bottom : 70, W = g.innerWidth || 1200;
    return { left: 20, top: Math.round(top + 18), bottom: 118, width: Math.round(Math.max(248, Math.min(340, W * 0.19))) };
  }
  function deckSync() { if (!X.deck) return; var on = deckOn(); if (on) X.deck.setLayout(deckRect()); X.deck.show(on); }
  function evCh(i) { if (!X.evChOf) { X.evChOf = {}; X.M.chapterEvents.forEach(function (list, c) { list.forEach(function (k) { X.evChOf[k] = c; }); }); } return X.evChOf[i]; }
  function deckEvent(i) { var e = X.G.events[i], c = evCh(i), ch = c != null ? X.M.chapters[c] : null; return e ? { no: ch ? ch.no : (c || 0) + 1, title: e.title || e.summary || '', key: DECK_KEY.test(e.kind || '') } : null; }
  function pickEvents(list, n) {
    list = list || []; if (list.length <= n) return list.slice();
    var out = list.filter(function (i) { return X.G.events[i] && DECK_KEY.test(X.G.events[i].kind || ''); }).slice(0, n), seen = {}, k, i;
    out.forEach(function (x) { seen[x] = 1; });
    for (k = 0; out.length < n && k < n * 2; k++) { i = list[Math.round(k * (list.length - 1) / (n * 2 - 1))]; if (!seen[i]) { seen[i] = 1; out.push(i); } }
    return out.sort(function (a, b) { return a - b; });
  }
  function castHex(name) {
    var S = X.scene(), n = S && S.nodeOf ? S.nodeOf('c:' + name) : null, info = S && S.skyInfo ? S.skyInfo() : null, TK = g.CLSkyTokens, camp = n && n.camp || '散星';
    if (!info || !TK) return null;
    for (var i = 0; i < info.sectors.length; i++) if (info.sectors[i].name === camp) return TK.hexCss(info.sectors[i].color);
    return null;
  }
  function deckData() {
    var TK = g.CLSkyTokens, lb = {}, lines = [], byKey = {};
    function no(c) { var ch = X.M.chapters[c]; return ch ? ch.no : c + 1; }
    function hex(gen, kind) { var c = TK.GEN[(gen | 0) % TK.GEN.length]; return kind === 'quiet' ? TK.mix(TK.C.INK3, c, 0.35) : kind === 'named' ? TK.mix(c, TK.C.INK2, 0.12) : c; }
    function one(l, kind) {
      return { id: String(l.id), kind: kind, label: l.label || '', c0: l.c0, c1: l.c1, no0: no(l.c0), no1: no(l.c1), span: l.c1 - l.c0 + 1, events: l.n, cast: l.cast || [], gen: l.gen,
        mainId: kind === 'main' || l.mainId == null ? null : String(l.mainId), mainLabel: kind === 'main' ? '' : lb[l.mainId] || '', resolved: !!l.resolved, suspended: !!l.suspended, derived: !!l.derived,
        theme: l.title && l.title.indexOf(' · ') < 0 && l.title !== l.label ? l.title : '', eventIdx: pickEvents(l.events, 6), color: hex(l.gen, kind) };
    }
    X.M.mains.forEach(function (m) { lb[m.id] = m.label; lines.push(one(m, 'main')); });
    X.M.lines.forEach(function (l) { lines.push(one(l, l.named ? 'named' : 'quiet')); });
    var cards = CLSkyDeckModel.build(lines, { unit: X.unit() }), nb = 0, nt = 0;
    X.deckKeyOf = {};
    cards.forEach(function (c) { byKey[c.key] = c; });
    cards.forEach(function (c) {
      if (c.type === 'twig') { nt += c.members.length; var m = byKey[c.mainKey]; c.color = TK.mix(TK.C.INK3, m ? m.color : TK.C.INK2, 0.4); c.members.forEach(function (id) { X.deckKeyOf[id] = c.key; }); }
      else { if (c.type === 'branch') nb++; X.deckKeyOf[c.id] = c.key; }
    });
    return { cards: cards, meta: { nCh: X.M.nCh, mains: X.M.mains.length, branches: nb + nt, twigs: nt } };
  }
  function deckHover(id) {
    if (!X.disc || !X.plot) return;
    var info = id ? X.disc.lineInfo(String(id)) : null;
    X.deckInfo = info; X.disc.hoverLine(info ? info.id : null);
    if (g.CLSkyDeep) CLSkyDeep.lineHover(info || X.selInfo || null);
    if (info) X.light(info.cast.slice(0, 14)); else if (X.selInfo) X.light(X.selInfo.cast.slice(0, 14)); else { var c = X.disc.cursor(); X.light(c != null ? X.M.chapterCast[c] : null); }
  }
  function deckOpen(card) {
    if (!X.disc || X.deckBusy) return;
    X.deckBusy = true;
    try { X.disc.focus(card && card.type !== 'twig' ? card.id : null); } finally { X.deckBusy = false; }
    if (card && card.type === 'twig') X.light(card.cast.slice(0, 14));
  }
  function ensureDeck() {
    if (X.deck || !g.CLSkyDeck || !g.CLSkyDeckModel) return X.deck;
    X.deck = CLSkyDeck.create({ host: X.hud || X.doc.body, unit: X.unit(), onHover: deckHover, onOpen: deckOpen, eventInfo: deckEvent, castColor: castHex,
      lineInfo: function (id) { return X.disc ? X.disc.lineInfo(String(id)) : null; },
      onSeek: function (c) { X.stopPlay(); X.seek(c); }, onPlay: function (c) { X.seek(c); if (!X.playing) X.togglePlay(); } });
    return X.deck;
  }
    return {
      deckOn: deckOn,
      deckRect: deckRect,
      deckSync: deckSync,
      evCh: evCh,
      deckEvent: deckEvent,
      pickEvents: pickEvents,
      castHex: castHex,
      deckData: deckData,
      deckHover: deckHover,
      deckOpen: deckOpen,
      ensureDeck: ensureDeck
    };
  }
  g.CLSkyShellDeck = { create: create };
})(window);
