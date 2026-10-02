/*!
 * @role component
 * @owns js/sky/sky-openfuse.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 开篇语汇融合（Q8.3 环节融合 A）：把揭幕那套「描出 / 打字 / 掠光」用回日常环节，不新造语汇、不改宿主文件。
 *  · 星盘开启：刻度数字逐个打出（沿用 .skd-type 的 --i 节拍）。关掉星盘就摘掉标记，下次开启重放。
 *    环线描出与彗头沿主环**不在这里做** —— 光层 sky-rings 早就有：sky-deep 开启星盘时 rings.reveal(0) 后
 *    按 DUR.unfurl 补间到 1，着色器里 uReveal 按角向切出描出的前沿、uFront 在同一处点一枚亮头（就是彗头）。
 *    SVG 的 .sd-ring / .sd-arc 在 body.skd-gl 下根本不写 d，往上加 class 是空转，所以这里不碰。
 *  · 悬停卡（#skyCard）：标题逐字（CLSkyUtil.type）+ 掠光类；卡边描出一圈（.is-fused::after）。
 *  · 卡片叠展开（剧情卡片叠 .skd-deck / 分组卡片叠 .skg-deck）：认到新建的展开体 → 这张卡的名字逐字打出，打完还原纯文本。
 *  · 罗盘开启（Q8.4）：把这个人**真实的**关系人名与关键事件名用 CLSkyRain.converge 从四周汇聚进晶体中心
 *    （中心取 S.crownScreenBounds()，文字全部来自图谱，不编）；轴签（#labels .cl-lab.gem-slot 的 .ln）逐字打出。
 * 只加 class 与 CSS 变量，不写宿主 JS；靠 MutationObserver 认出「这一刻发生了什么」，不开 rAF / setInterval。
 * 降级：减弱动效或 low 档一律不加标记（元素直接是终态），CSS 侧也有兜底。
 * CLSkyOpenFuse = { stats() }
 */
(function (g) {
  'use strict';
  var doc = g.document;
  if (!doc || !doc.body) return;

  var BC = doc.body.classList, U = null, plotOn = false, cardHost = null, cardObs = null;
  var compOn = false, rain = null, rainHost = null, pend = 0, flowed = false, hooked = null;
  var st = { plots: 0, nums: 0, titles: 0, cards: 0, skipped: 0, comps: 0, flows: 0, axes: 0, unfolds: 0 };

  function util() { return U || (U = g.CLSkyUtil); }
  function TK() { return g.CLSkyTokens; }
  function still() {
    var T = TK();
    if (T && T.reduced && T.reduced()) return true;
    var d = doc.querySelector('.skd-loader') || doc.body;
    if (BC.contains('skylab-still')) return true;
    return d.getAttribute && d.getAttribute('data-tier') === 'low';
  }

  /* ── 星盘开启：环描出 + 彗头 + 刻度数字打字 ───────────── */
  function discSvg() { return doc.querySelector('svg.sky-disc'); }

  function typeNums(svg) {
    var ns = svg.querySelectorAll('.sd-num'), i;
    for (i = 0; i < ns.length; i++) {
      ns[i].style.setProperty('--i', i);
      ns[i].classList.add('is-typing');
    }
    st.nums += ns.length;
  }

  function clearDisc(svg) {
    var all = svg.querySelectorAll('.is-typing'), i;
    for (i = 0; i < all.length; i++) { all[i].classList.remove('is-typing'); }
  }

  function onPlot(on) {
    var svg;
    if (on === plotOn) return;
    plotOn = on;
    svg = discSvg();
    if (!svg) return;
    if (!on) { clearDisc(svg); return; }
    if (still()) { st.skipped++; return; }
    st.plots++;
    typeNums(svg);
  }

  /* ── 罗盘开启：真实名字汇聚入晶体 + 轴签打字 ───────────── */
  /* 取这个人的真实关系人名与关键事件名（只读图谱，取不到就少几条，不编） */
  function flowItems(who) {
    var G = g.CLApp && CLApp.graph && CLApp.graph(), out = [], seen = {}, rs, i, r, o, ev;
    if (!G || !who) return out;
    rs = G.relations || [];
    for (i = 0; i < rs.length && out.length < 14; i++) {
      r = rs[i]; o = r.a === who ? r.b : r.b === who ? r.a : null;
      if (!o || seen[o]) continue;
      seen[o] = 1; out.push(o);
    }
    ev = G.events || [];   /* 事件字段是 title + characters（不是 name / actors），照图谱取，不编 */
    for (i = 0; i < ev.length && out.length < 22; i++) {
      if (!ev[i] || !ev[i].title || !ev[i].characters) continue;
      if (ev[i].characters.indexOf(who) >= 0) out.push(ev[i].title);
    }
    return out;
  }

  /* crownScreenBounds() 给的是 {left,right,top,bottom}（不是 box），晶体还没成形时宽高为 0 */
  function crownCenter() {
    var S = g.CLApp && CLApp.scene && CLApp.scene(), b = S && S.crownScreenBounds ? S.crownScreenBounds() : null;
    if (!b || !(b.right > b.left) || !(b.bottom > b.top)) return null;
    return [(b.left + b.right) / 2, (b.top + b.bottom) / 2];
  }

  function typeAxes() {
    var ls = doc.querySelectorAll('#labels .cl-lab.gem-slot .ln'), u = util(), i, t;
    if (!u || !u.type || !ls.length) return false;
    for (i = 0; i < ls.length; i++) {
      t = ls[i];
      if (t.__fused || !t.textContent) continue;
      t.__fused = 1;
      t.style.setProperty('--type-d0', (i * 0.035).toFixed(3) + 's');
      u.type(t, t.textContent, { caret: false });
      st.axes++;
    }
    return true;
  }

  /* 开罗盘那一刻晶体还没成形、轴签也还没建出来（实测要 2 s 上下），所以不能在 class 翻转那一帧就做。
     挂宿主的帧钩子等它们出现，做完即熄；平时只是一次布尔判断。不开自己的 rAF。 */
  function tryCompass() {
    var c, items, who, done = true;
    if (!typeAxes()) done = false;
    who = g.CLSky && CLSky.state ? CLSky.state().compass : null;
    c = crownCenter();
    items = flowItems(who);
    if (c && items.length && g.CLSkyRain) {
      if (!rain) {
        rainHost = doc.querySelector('.sky-shell') || doc.body;
        rain = g.CLSkyRain.mount(rainHost, { cls: 'is-compass' });
      }
      if (rain && !flowed) { flowed = true; st.flows += rain.converge(items, c[0], c[1]) || 0; }
    } else { done = false; }
    return done;
  }

  /* 窗口内每帧都试：轴签是分批建出来的（实测先 4 个、随后补到 16），第一次成功就收手会漏掉后来的。
     汇聚只发一次（flowed 挡着），轴签逐个补打，打过的有 __fused 标记不会重打。 */
  function tick(dt) {
    if (pend <= 0) return;
    pend -= (dt > 0 && dt < 1) ? dt : 0.016;
    if (!compOn) { pend = 0; return; }
    tryCompass();
  }

  function hookScene() {
    var sc = g.CLScene && CLScene.current;
    if (!sc || !sc.registerFrameHook || sc === hooked) return;
    hooked = sc; sc.registerFrameHook(tick);
  }

  function onCompass(on) {
    if (on === compOn) return;
    compOn = on;
    if (!on) { pend = 0; flowed = false; if (rain) rain.clear(); return; }
    if (still()) { st.skipped++; return; }
    st.comps++;
    flowed = false;
    hookScene();
    pend = 4;   /* 最多跟 4 s，之后不再管，不赖着 */
    tryCompass();
  }

  /* ── 卡片：标题逐字 + 顶缘掠光 + 卡边描出 ───────────── */
  function dressCard(card) {
    var t, u;
    if (!card || card.__fused) return;
    card.__fused = 1;
    if (still()) { st.skipped++; return; }
    card.classList.add('is-fused');
    st.cards++;
    t = card.querySelector('.skd-card__title');
    u = util();
    if (t && u && u.type && t.textContent) {
      u.type(t, t.textContent, { caret: false });
      t.classList.add('is-glint');
      st.titles++;
    }
  }

  function scanCards(root) {
    var cs = root.querySelectorAll ? root.querySelectorAll('.skd-card') : [], i;
    if (root.classList && root.classList.contains('skd-card')) dressCard(root);
    for (i = 0; i < cs.length; i++) dressCard(cs[i]);
  }

  /* ── 接线：body 类变化认星盘开关；卡片宿主认新卡 ───────────── */
  function wireCards() {
    var host = doc.getElementById('skyCard');   /* sky-shell 建的 .sky-card#skyCard，CLSkyCards.mount 往里塞卡 */
    if (!host || host === cardHost) return;
    cardHost = host;
    if (cardObs) cardObs.disconnect();
    cardObs = new MutationObserver(function (recs) {
      var i, j, n;
      for (i = 0; i < recs.length; i++) {
        for (j = 0; j < recs[i].addedNodes.length; j++) {
          n = recs[i].addedNodes[j];
          if (n.nodeType === 1) scanCards(n);
        }
      }
    });
    cardObs.observe(cardHost, { childList: true, subtree: true });
    scanCards(cardHost);
  }

  /* ── 卡片叠展开（剧情卡片叠 .skd-deck · 分组卡片叠 .skg-deck）：展开体只在展开那一刻建出来，
       认到新建的展开体就把这张卡的名字逐字打出（+ is-glint / is-unfold 给掠光留钩子）；打完还原成纯文本，省略号照常 ── */
  var decks = [];
  function onUnfold(bd) {
    var c = bd.parentNode, nm = c && c.querySelector('.skd-card__name'), u = util(), t, tt;
    if (!nm || !(t = nm.textContent)) return;
    if (still() || !u || !u.type) { st.skipped++; return; }
    tt = u.type(nm, t, { cps: 36 });   /* 卡名短：约 28 ms 一字，一拍打完 */
    nm.classList.add('is-glint'); c.classList.add('is-unfold');
    st.unfolds++;
    setTimeout(function () {
      if (nm.textContent === t) { nm.textContent = t; nm.classList.remove('skd-type', 'is-glint'); }
      c.classList.remove('is-unfold');
    }, Math.round(tt * 1000) + 900);
  }
  function wireDecks() {
    var hs = doc.querySelectorAll('.skd-deck, .skg-deck'), i;
    for (i = 0; i < hs.length; i++) {
      if (decks.indexOf(hs[i]) >= 0) continue;
      decks.push(hs[i]);
      new MutationObserver(function (recs) {
        var a, b, n;
        for (a = 0; a < recs.length; a++) for (b = 0; b < recs[a].addedNodes.length; b++) {
          n = recs[a].addedNodes[b];
          if (n.nodeType === 1 && (n.classList.contains('skd-card__body') || n.classList.contains('skg-card__body'))) onUnfold(n);
        }
      }).observe(hs[i], { childList: true, subtree: true });
    }
  }

  new MutationObserver(function () {
    onPlot(BC.contains('sky-plot-on'));
    onCompass(BC.contains('sky-compass-on'));
    wireCards(); wireDecks(); wireHud();
  }).observe(doc.body, { attributes: true, attributeFilter: ['class'], childList: true });
  /* 卡片叠建在 #skyHud 里，常在 body 类最后一次变化之后才建（分组卡片叠就是）：盯 HUD 的直接子节点，新叠一出现就接上 */
  var hudEl = null;
  function wireHud() {
    var h = doc.getElementById('skyHud');
    if (!h || h === hudEl) return;
    hudEl = h;
    new MutationObserver(function () { wireCards(); wireDecks(); }).observe(h, { childList: true });
  }
  wireHud();

  wireCards(); wireDecks();
  onPlot(BC.contains('sky-plot-on'));
  onCompass(BC.contains('sky-compass-on'));

  g.CLSkyOpenFuse = {
    stats: function () { var o = {}, k; for (k in st) o[k] = st[k]; o.plotOn = plotOn; o.compOn = compOn; o.rain = !!rain; o.cardHost = !!cardHost; o.glRings = BC.contains('skd-gl'); return o; },
    /* 测试钩子：换分组 / 换书之后重新认一遍盘面与卡片宿主 */
    rescan: function () { plotOn = false; wireCards(); wireDecks(); onPlot(BC.contains('sky-plot-on')); return this.stats(); }
  };
})(window);
