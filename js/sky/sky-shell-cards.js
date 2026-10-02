/**
 * @role shell-cards
 * @owns js/sky/sky-shell-cards.js
 * 剧情线浮卡、停靠位置与参与者点亮。状态由 sky-shell 持有，X 是显式闭包桥；不创建帧循环。
 */
(function (g) {
  'use strict';
  function create(X) {
  function castLine(info) { var c = info.cast || [], s = c.slice(0, 6).join('、'); return c.length > 6 ? s + ' 等 ' + c.length + ' 人' : s; }
  function cardHtml(info) {
    var kind = info.kind === 'main' ? '主线' : info.kind === 'twig' ? '细支' : '支线';
    return '<div class="sc-k g' + info.gen + '">' + kind + (info.kind !== 'main' && info.mainLabel ? ' · 属「' + X.esc(info.mainLabel) + '」段' : '') + (info.derived ? ' · 算法归纳' : '') + '</div>' +
      '<div class="sc-t">' + X.esc(info.label) + (info.theme ? '<small class="sc-theme">' + X.esc(info.theme) + '</small>' : '') + '</div>' +
      '<div class="sc-m">第 ' + info.no0 + (info.no1 !== info.no0 ? '–' + info.no1 : '') + ' 回 · <b>' + info.span + '</b> 回 · ' + info.events + ' 事件 · ' + (info.cast || []).length + ' 人' + (info.resolved ? ' · 收束' : info.suspended ? ' · 悬置' : '') + '</div>' +
      '<div class="sc-c">' + X.esc(castLine(info)) + '</div>';
  }
  function showCard(info, x, y) {
    var node = g.CLSkyDeep && CLSkyDeep.enabled() ? CLSkyDeep.lineCard(info) : null;
    if (node) { X.el.skyCard.textContent = ''; X.el.skyCard.appendChild(node); } else X.el.skyCard.innerHTML = cardHtml(info);
    X.el.skyCard.hidden = false; placeCard(x, y);
  }
  function placeCard(x, y) {
    var W = g.innerWidth, H = g.innerHeight;
    // 窄屏：浮卡会盖住半个盘面 → 停靠在底栏上方整宽
    var dock = W <= 560;
    X.el.skyCard.classList.toggle('is-dock', dock);
    var w = X.el.skyCard.offsetWidth || 240, h = X.el.skyCard.offsetHeight || 90;
    if (dock) {
      var anchor = [X.el.skyLegend, X.el.skyPlayer].filter(function (n) { return n && !n.hidden && n.offsetHeight; })[0];
      var floor = anchor ? anchor.getBoundingClientRect().top : H - 96;
      X.el.skyCard.style.setProperty('--sc-x', '12px');
      X.el.skyCard.style.setProperty('--sc-y', Math.max(72, floor - h - 8).toFixed(0) + 'px');
      return;
    }
    var left = x + 18, top = y + 16;
    if (left + w > W - 12) left = x - w - 18;
    if (top + h > H - 96) top = y - h - 16;
    X.el.skyCard.style.setProperty('--sc-x', Math.max(12, left).toFixed(0) + 'px');
    X.el.skyCard.style.setProperty('--sc-y', Math.max(72, top).toFixed(0) + 'px');
  }
  function hideCard() { if (X.el.skyCard) X.el.skyCard.hidden = true; }
  function light(names) { var S = X.scene(); if (!S) return; if (names && names.length) { S.setSearchSet(names); S.setCastDim(1); } else { S.setSearchSet(null); S.setCastDim(X.plot ? X.PLOT_DIM : 0); } if (g.CLSkyDeep) CLSkyDeep.light(names && names.length ? names : null); }
  function onDiscHover(p) {
    X.hoverInfo = p && p.info;
    /* 卡片叠收着时（星座 / 罗盘）同一个 id 不再重排：收着的卡片叠每次重排都要读一次视口高（整页同步布局，进出罗盘各 2–11 ms） */
    var hid = X.hoverInfo ? X.hoverInfo.id : null;
    if (X.deck && (hid !== X.deckHotSent || X.deckOn())) X.deck.hot(hid);
    X.deckHotSent = hid;
    if (g.CLSkyDeep) CLSkyDeep.lineHover(X.hoverInfo || X.selInfo || null);
    if (X.hoverInfo) { showCard(X.hoverInfo, p.x, p.y); light(X.hoverInfo.cast.slice(0, 14)); }
    else if (X.selInfo) { light(X.selInfo.cast.slice(0, 14)); hideCard(); }
    else { hideCard(); var c = X.disc && X.disc.cursor(); light(c != null ? X.M.chapterCast[c] : null); }
  }
  function onDiscSelect(info) {
    X.selInfo = info;
    if (g.CLSkyDeep) CLSkyDeep.lineHover(info || X.hoverInfo || null);
    /* 盘上点选一条线 → 卡片叠展开同一张（从卡片叠发起的选中不再弹浮卡：卡片本身就是详情） */
    if (X.deck && !X.deckBusy) { X.deckBusy = true; try { X.deck.open(info ? X.deckKeyOf[info.id] || null : null); } finally { X.deckBusy = false; } }
    if (info) { light(info.cast.slice(0, 14)); var p = X.deckBusy || X.deckOn() ? null : X.disc.lineScreen(info.id); if (p) showCard(info, p[0], p[1]); else hideCard(); }
    else { hideCard(); light(null); }
  }
    return {
      castLine: castLine,
      cardHtml: cardHtml,
      showCard: showCard,
      placeCard: placeCard,
      hideCard: hideCard,
      light: light,
      onDiscHover: onDiscHover,
      onDiscSelect: onDiscSelect
    };
  }
  g.CLSkyShellCards = { create: create };
})(window);
