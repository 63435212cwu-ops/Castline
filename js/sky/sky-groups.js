/*!
 * @role groups
 * @owns js/sky/sky-groups.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 分组卡片叠（星座态左侧）：按当前分类（阵营 / 立场 / 身份）每组一张卡，与剧情卡片叠同一语汇——层叠只露标题条、点开看全部。
 *  · 悬停卡 → 该组星云提亮、成员点亮、团名亮起；悬停图上的团名 / 星 → 对应的卡亮起并滚到眼前（双向）。
 *  · 点成员名 → 进其罗盘；「聚焦此团」= 点团名的同一条路径（其余压暗，再点取消）。
 *  · 版位：与剧情卡片叠同一左栏；星图外接圆压到左栏时默认收起成标题条（点标题展开）；窄屏收成底部抽屉。
 *  · 键盘：↑↓ 换卡 · Home / End · Enter / 空格 展开收起 · Esc 收起。不私开 rAF：挂 scene 帧钩子只比对星域几何换没换。
 */
(function (g) {
  'use strict';
  var doc = g.document, U = null, T = null;

  function create(opts) {
    opts = opts || {};
    U = g.CLSkyUtil; T = g.CLSkyTokens;
    var mk = U.mk, data = null, cards = [], by = {}, ok = null, hk = null, fk = null, label = '阵营', unit = opts.unit || '回';
    var fold = false, userFold = null, shown = false, dead = false, oT = 0, eT = 0;

    var side = mk('aside', 'skg-deck', opts.host || doc.body);   /* 不带 skd-deck：那一套有窄屏 38vh 等版位规则，只借它的子元素类 */
    side.setAttribute('aria-label', '分组卡片'); side.hidden = true;
    var head = mk('header', 'skd-deck__head skg-head', side);
    var tBtn = mk('button', 'skg-toggle', head); tBtn.type = 'button'; tBtn.setAttribute('aria-expanded', 'true');
    var title = mk('span', 'skd-deck__title', tBtn, '阵营卡');
    mk('i', 'skg-chev', tBtn);
    var cnt = mk('span', 'skd-deck__count', head);
    var vp = mk('div', 'skd-deck__viewport skg-viewport', side);
    vp.tabIndex = 0; vp.setAttribute('role', 'listbox'); vp.setAttribute('aria-label', '分组');
    var list = mk('div', 'skg-list', vp);
    tBtn.addEventListener('click', function () { userFold = !fold; setFold(userFold); }, false);

    function hex(n) { return T && T.hexCss ? T.hexCss(n) : '#' + ('000000' + (n >>> 0).toString(16)).slice(-6); }
    var X = { mk: mk, doc: doc, hex: hex, num: U.num, unit: unit, label: label,
      chNo: function (c) { return opts.chNo ? opts.chNo(c) : c + 1; },
      onPick: function (nm) { if (opts.onPick) opts.onPick(nm); },
      onFocus: function (nm) { if (opts.onFocus) opts.onFocus(nm); paint(); },
      posOf: function (nm) { return opts.posOf ? opts.posOf(nm) : null; },
      viewOf: function () { return opts.viewOf ? opts.viewOf() : null; },
      remeasure: function () {} };

    function node(gp, i, nAll) {
      var n = mk('article', 'skd-card skg-card' + (gp.field ? ' is-field' : '') + (gp.core ? ' is-core' : ''));
      n.setAttribute('role', 'option'); n.setAttribute('data-key', gp.name); n.setAttribute('aria-expanded', 'false');
      n.style.setProperty('--c', hex(gp.hex)); n.style.setProperty('--i', String(i)); n.style.setProperty('--d', String(Math.max(0, nAll - 1 - i))); n.style.setProperty('--share', gp.share.toFixed(4));
      var bar = mk('div', 'skd-card__bar skg-bar', n);
      mk('i', 'skd-card__sigil', bar);
      mk('span', 'skd-card__name', bar, gp.name).title = gp.name;
      /* 收起时标题条也报出最重的几位（按星等权重，与展开体 α/β/γ 同序）：一眼知道这团是谁 */
      for (var j = 0, ln = []; j < gp.members.length && j < 3; j++) ln.push(gp.members[j].name);
      if (ln.length) mk('span', 'skg-bar__leads', bar, ln.join(' · ')).title = ln.join(' · ');
      bar.title = gp.name + ' · ' + gp.count + ' 人' + (ln.length ? ' · ' + ln.join(' · ') : '');
      mk('span', 'skd-card__span', bar, gp.count + ' 人');
      mk('i', 'skg-share', bar);
      var r = { n: n, g: gp, bd: null, i: i };
      bar.addEventListener('pointerenter', function () { hov(r, true); }, false);
      bar.addEventListener('pointerleave', function () { hov(r, false); }, false);
      n.addEventListener('pointerleave', function () { hov(r, false); }, false);
      bar.addEventListener('click', function () { setOpen(ok === gp.name ? null : gp.name); }, false);
      return r;
    }
    function hov(r, on) {
      if (on) { hk = r.g.name; fk = r.g.name; if (opts.onHover) opts.onHover(r.g.name); }
      else if (hk === r.g.name) { hk = null; if (opts.onHover) opts.onHover(null); }
      paint();
    }
    function paint() {
      for (var i = 0; i < cards.length; i++) {
        var r = cards[i], c = r.n.classList, nm = r.g.name, sel = opts.selected ? opts.selected() : null;
        c.toggle('is-open', nm === ok); c.toggle('is-hot', nm === hk); c.toggle('is-focus', nm === fk); c.toggle('is-sel', nm === sel);
        r.n.setAttribute('aria-expanded', nm === ok ? 'true' : 'false');
        r.n.setAttribute('aria-selected', nm === fk ? 'true' : 'false');
        if (nm === ok && !r.bd) g.CLSkyGroupsBody.build(r, X);
        else if (nm !== ok && r.bd) { if (r.bd.parentNode) r.bd.parentNode.removeChild(r.bd); r.bd = null; }
      }
    }
    function setOpen(nm) {
      if (nm === ok) return;
      ok = nm; if (nm) fk = nm;
      paint();
      if (nm) see(nm, true);
      if (opts.onOpen) opts.onOpen(nm);
    }
    /* 滚到眼前：只在卡不在视口里时滚（展开卡把标题条滚到顶部附近） */
    function see(nm, top) {
      var r = by[nm]; if (!r || fold) return;
      var y = r.n.offsetTop, h = r.n.offsetHeight, st = vp.scrollTop, vh = vp.clientHeight;
      if (!top && y >= st && y + Math.min(h, 60) <= st + vh) return;
      var to = Math.max(0, top ? y - 8 : y - vh * 0.3);
      try { vp.scrollTo({ top: to, behavior: U.reduced() ? 'auto' : 'smooth' }); } catch (e) { vp.scrollTop = to; }
    }
    function setData(d, meta) {
      meta = meta || {};
      data = d; label = meta.label || '阵营'; X.label = label; unit = meta.unit || unit; X.unit = unit;
      cards = []; by = {}; ok = hk = fk = null;
      while (list.firstChild) list.removeChild(list.firstChild);
      var gs = d && d.groups ? d.groups.slice() : [];
      gs.sort(function (a, b) { return (b.core ? 1 : 0) - (a.core ? 1 : 0) || (a.field ? 1 : 0) - (b.field ? 1 : 0) || a.idx - b.idx; });   /* 盘心团在前、散星在后，其余按图上自 12 点顺时针 */
      for (var i = 0; i < gs.length; i++) { var r = node(gs[i], i, gs.length); cards.push(r); by[gs[i].name] = r; list.appendChild(r.n); }
      title.textContent = label + '卡';
      cnt.textContent = gs.length + ' 组 · ' + U.num(d ? d.total : 0) + ' 人';
      vp.setAttribute('aria-label', label);
      vp.scrollTop = 0;
      paint();
      if (shown) enter();
    }
    function setFold(v) {
      fold = !!v;
      side.classList.toggle('is-folded', fold);
      tBtn.setAttribute('aria-expanded', fold ? 'false' : 'true');
      tBtn.title = fold ? '展开' + label + '卡' : '收起' + label + '卡';
    }
    function enter() {
      if (U.reduced()) return;
      side.classList.remove('is-entering'); void side.offsetWidth; side.classList.add('is-entering');
      if (eT) g.clearTimeout(eT);
      eT = g.setTimeout(function () { eT = 0; side.classList.remove('is-entering'); }, 1400);
    }
    function show(on) {
      on = !!on; if (on === shown) return;
      shown = on;
      if (oT) { g.clearTimeout(oT); oT = 0; }
      if (on) {
        side.hidden = false;
        oT = g.setTimeout(function () { oT = 0; if (dead) return; side.classList.add('is-on'); enter(); }, 0);
      } else { side.classList.remove('is-on', 'is-entering'); side.hidden = true; if (hk && opts.onHover) opts.onHover(null); hk = null; }
    }
    /* 版位：与剧情卡片叠同一左栏；tight = 星图外接圆压进左栏 → 默认收起成标题条（用户手动开合过就听用户的） */
    function setLayout(o, tight) {
      o = o || {};
      if (o.left != null) side.style.setProperty('--skd-deck-left', o.left + 'px');
      if (o.top != null) side.style.setProperty('--skd-deck-top', o.top + 'px');
      if (o.bottom != null) side.style.setProperty('--skd-deck-bottom', o.bottom + 'px');
      if (o.width != null) side.style.setProperty('--skd-deck-w', o.width + 'px');
      setFold(userFold != null ? userFold : !!tight);
    }
    /* 图上悬停团名 / 星 → 卡亮起（soft = 星所属的组：只亮不滚） */
    function hot(nm, soft) {
      if (nm === hk) return;
      hk = nm && by[nm] ? nm : null;
      paint();
      if (hk && !soft) see(hk, false);
    }
    function onKey(e) {
      var k = e.key, i = -1, j;
      /* 成员/动作按钮保留原生 Enter 与空格点击，不由卡片叠截走，也不漏给全局播放键。 */
      if ((k === 'Enter' || k === ' ') && e.target !== vp && e.target.closest && e.target.closest('button')) { e.stopPropagation(); return; }
      for (j = 0; j < cards.length; j++) if (cards[j].g.name === fk) i = j;
      if (k === 'ArrowDown' || k === 'ArrowUp' || k === 'Home' || k === 'End') {
        i = k === 'Home' ? 0 : k === 'End' ? cards.length - 1 : Math.max(0, Math.min(cards.length - 1, i + (k === 'ArrowDown' ? 1 : -1)));
        fk = cards[i] ? cards[i].g.name : null;
        if (fk && opts.onHover) opts.onHover(fk);
        hk = fk; paint(); see(fk, false);
      } else if (k === 'Enter' || k === ' ') { if (fk) setOpen(ok === fk ? null : fk); }
      else if (k === 'Escape') { if (ok) setOpen(null); else vp.blur(); }
      else return;
      e.preventDefault(); e.stopPropagation();   /* 卡片叠自己处理的键不再往下传（方向键在图上是旋转） */
    }
    vp.addEventListener('keydown', onKey, false);
    vp.addEventListener('blur', function () { if (hk && opts.onHover) opts.onHover(null); hk = null; paint(); }, false);

    return {
      el: side, setData: setData, show: show, setLayout: setLayout, hot: hot, open: function (nm) { setOpen(nm || null); }, fold: function (v) { userFold = v == null ? null : !!v; setFold(v == null ? fold : !!v); },
      stats: function () {
        return { shown: shown, folded: fold, cards: cards.length, open: ok, hot: hk, focus: fk, label: label,
          body: ok && by[ok] && by[ok].bd ? { chips: by[ok].bd.querySelectorAll('.skg-card__chip:not(.is-more)').length, leads: by[ok].bd.querySelectorAll('.skg-card__lead').length } : null };
      },
      dispose: function () { dead = true; if (oT) g.clearTimeout(oT); if (eT) g.clearTimeout(eT); if (side.parentNode) side.parentNode.removeChild(side); cards = []; by = {}; }
    };
  }

  g.CLSkyGroups = { create: create };
})(window);
