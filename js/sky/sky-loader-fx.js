/*!
 * @role openfx
 * @owns js/sky/sky-loader-fx.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 *
 * 读取幕的开篇语汇（参考开篇视频）：字符数据流 · 四角微字与发丝准星 · 真实五步清单（READ / PARSE / LAYOUT / LIGHT / REVEAL）
 * · 真实计数启动日志（逐行打字 + 块光标）· 书名逐字金属掠光 · 刻度环外倾斜椭圆彗星轨（每推进一步掠过一次）。
 *
 * 只依据材料：日志、角标里的书名与数字全部来自宿主传进来的真实读数；读完材料之前的字符雨只是数字与星号。
 * 纪律：ES5；不开 rAF / setInterval；动画全在合成层（CSS 关键帧 / 一次性 Web Animations）；类名前缀 skd-open；
 * 动态值只走 style.setProperty；减弱动效直达终态；low 档不下雨、不跑彗星。
 */
(function (g) {
  'use strict';
  var U = g.CLSkyUtil;
  var EN = { fetch: 'READ', analyze: 'PARSE', layout: 'LAYOUT', compile: 'LIGHT', reveal: 'REVEAL' };
  var VERB = { fetch: '读取材料', analyze: '推演剧情线', layout: '排布星座', compile: '点亮光层', reveal: '揭幕' };
  var MAXLOG = 7;

  function O() { var t = g.CLSkyTokens && g.CLSkyTokens.OPEN; return t || { type: { cps: 12.5, log: 28, glint: 0.9, blinks: 6 }, comet: { pass: 1.8, tail: 0.22 } }; }

  function attach(root, dom) {
    var tier = 'high', logClock = 0, lines = [], passes = 0, typedEnd = 0, lastStage = '', titleText = '';
    root.classList.add('is-cine');

    /* 字符数据流：垫在盘与文字下面 */
    var rain = g.CLSkyRain ? g.CLSkyRain.mount(root, { cls: 'is-loader' }) : null;
    if (rain && dom.sky && dom.sky.nextSibling) root.insertBefore(rain.el, dom.sky.nextSibling);

    /* 四角微字 */
    function corner(pos) { return U.mk('div', 'skd-open__corner is-' + pos, root); }
    var tl = corner('tl'), tr = corner('tr'), bl = corner('bl'), br = corner('br');
    var tlHead = U.mk('div', 'skd-open__brand', tl);
    U.mk('b', null, tlHead, 'CASTLINE'); U.mk('i', 'skd-open__rule', tlHead); U.mk('span', 'skd-open__cross', tlHead, '+');
    U.mk('div', 'skd-open__micro', tl, '角色星图 · CHARACTER STAR ATLAS');
    var trTitle = U.mk('div', 'skd-open__micro is-title', tr), trCount = U.mk('div', 'skd-open__micro', tr, '— · —');
    U.mk('i', 'skd-open__rule is-short', tr);
    U.mk('div', 'skd-open__micro', bl, '每一颗星都来自原文');
    U.mk('div', 'skd-open__micro is-en', bl, 'EVERY STAR FROM THE TEXT');
    var brPct = U.mk('div', 'skd-open__pct', br, '000%');
    U.mk('i', 'skd-open__rule is-short', br);

    /* 清单：沿用读取幕自己的步骤表（测试与读屏都读它），这里只补英文码并挪到幕根下（文字组有位移变换，不能做它的定位容器） */
    var i, steps = dom.items && dom.items.length ? dom.items[0].parentNode : null;
    if (steps) root.appendChild(steps);
    for (i = 0; dom.items && i < dom.items.length; i++) {
      var k = dom.items[i].getAttribute('data-k');
      if (EN[k]) dom.items[i].setAttribute('data-en', EN[k]);
    }

    /* 书名下的斜杠副题 + 启动日志 */
    var kicker = U.mk('div', 'skd-open__kicker');
    U.mk('span', 'skd-open__slash', kicker, '//////');
    U.mk('span', 'skd-open__kick-zh', kicker, '角色星图');
    U.mk('span', 'skd-open__slash', kicker, '//////');
    var kickEn = U.mk('div', 'skd-open__kick-en', null, 'CHARACTER  STAR  ATLAS');
    if (dom.title && dom.title.parentNode) { dom.title.parentNode.insertBefore(kicker, dom.title.nextSibling); kicker.parentNode.insertBefore(kickEn, kicker.nextSibling); }
    var logEl = U.mk('ol', 'skd-open__log', dom.detail && dom.detail.parentNode ? dom.detail.parentNode : root);
    logEl.setAttribute('aria-hidden', 'true');

    /* 彗星轨：倾斜椭圆（外框定倾角与扁率），转子每推进一步掠过一圈（一次性） */
    var orbit = U.mk('div', 'skd-open__orbit', dom.dial || root);
    U.mk('div', 'skd-open__track', orbit);
    var rotor = U.mk('div', 'skd-open__rotor', orbit);
    U.mk('i', 'skd-open__head', rotor);

    function still() { return U.reduced() || tier === 'low'; }
    function comet() {
      if (still() || !rotor.animate) return false;
      var c = O().comet;
      rotor.animate([{ transform: 'rotate(-20deg)', opacity: 0 }, { opacity: 1, offset: 0.12 }, { opacity: 1, offset: 0.82 }, { transform: 'rotate(340deg)', opacity: 0 }],
        { duration: Math.round(c.pass * 1000), easing: 'cubic-bezier(.45,.05,.25,1)', fill: 'none' });
      passes++;
      return true;
    }

    function log(text) {
      if (!text) return 0;
      var t = U.now(), delay = Math.max(0, logClock - t), li = U.mk('li', 'skd-open__line', logEl), body = U.mk('span', 'skd-open__txt', li);
      U.mk('span', 'skd-open__gt', li, '>');
      li.insertBefore(li.lastChild, body);
      if (lines.length) lines[lines.length - 1].body.classList.remove('has-caret');
      var tt = U.type(body, text, { cps: O().type.log, delay: delay, caret: true });
      logClock = t + tt; typedEnd = Math.max(typedEnd, logClock);
      lines.push({ li: li, body: body, text: String(text) });
      while (lines.length > MAXLOG) { var old = lines.shift(); if (old.li.parentNode) old.li.parentNode.removeChild(old.li); }
      return tt;
    }

    function show(meta) {
      meta = meta || {};
      logEl.textContent = ''; lines = []; logClock = 0; typedEnd = 0; lastStage = ''; passes = 0; titleText = '';
      trTitle.textContent = ''; trCount.textContent = '— · —'; brPct.textContent = '000%';
      if (rain) { rain.glyphs(null); rain.wave(); }
      if (meta.title) title(meta.title);
      comet();
    }
    function stage(key, frac, detail) {
      var f = Math.max(0, Math.min(1, +frac || 0));
      brPct.textContent = ('00' + Math.round(f * 100)).slice(-3) + '%';
      if (!key || key === lastStage) return;
      lastStage = key;
      if (rain) rain.pulse();
      comet();
      if (key !== 'reveal') log(VERB[key] ? VERB[key] + (detail ? ' · ' + detail : '') : (detail || key));
    }
    function title(t) {
      t = String(t == null ? '' : t);
      if (!t || t === titleText || !dom.title) return;
      titleText = t;
      var tt = U.type(dom.title, t, { cps: O().type.cps, glint: true, cls: 'skd-open__title' });
      typedEnd = Math.max(typedEnd, U.now() + tt + O().type.glint * 0.5);
      trTitle.textContent = t;
    }
    function counts(o) {
      o = o || {};
      var parts = [];
      if (o.chars != null) parts.push(U.num(o.chars) + ' 人');
      if (o.chapters != null) parts.push(U.num(o.chapters) + ' 回');
      if (parts.length) trCount.textContent = parts.join(' · ');
    }
    function finish() { log('ready'); }
    function glyphs(list) { return rain ? rain.glyphs(list) : 0; }
    /* 距书名与日志打完还有多少秒（宿主据此决定揭幕前幕再留多久） */
    function holdLeft() { return still() ? 0 : Math.max(0, typedEnd - U.now()); }
    function setTier(t) { tier = t || 'high'; if (rain) rain.setTier(tier); }
    function stats() {
      return { cine: root.classList.contains('is-cine'), log: lines.map(function (x) { return x.text; }), title: titleText, passes: passes,
        pct: brPct.textContent, count: trCount.textContent, rain: rain ? rain.stats() : null, holdLeft: +holdLeft().toFixed(2) };
    }
    return { show: show, stage: stage, title: title, log: log, counts: counts, finish: finish, glyphs: glyphs, holdLeft: holdLeft, setTier: setTier, stats: stats, rain: rain };
  }

  g.CLSkyLoaderFx = { attach: attach };
})(window);
