/*! 深空观星台 · 光层信息卡 DOM 构造器（纯函数 · 无状态）
 *  @role component
 *  @owns js/sky/sky-cards.js
 *  @budget kb<=7, drawcalls 0, points 0, vertices 0, rtpx 0, passes 0
 *  @contract deep-sky/1
 *  无自跑动画与内部状态 → 无需 reduced-motion / tier 降级路径（降级由 sky-view 侧决定是否挂载）。
 *  颜色 / 比例只写 --skd-* CSS 变量，颜色值一律取自 CLSkyTokens.hexCss；正文数据只走 textContent。
 */
(function (g) {
  'use strict';

  var KIND = { main: '主线', branch: '支线', twig: '细支' };

  function el(tag, cls) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    return e;
  }

  function add(parent, tag, cls, v) {
    var e = el(tag, cls);
    if (v !== undefined) { e.textContent = (v === null ? '' : String(v)); }
    parent.appendChild(e);
    return e;
  }

  function text(parent, v) {
    parent.appendChild(document.createTextNode(v === undefined || v === null ? '' : String(v)));
    return parent;
  }

  function hex(n) {
    var T = g.CLSkyTokens;
    if (!T || typeof T.hexCss !== 'function') { return ''; }
    return T.hexCss(n);
  }

  function cssVar(e, name, v) {
    if (e && e.style && e.style.setProperty) { e.style.setProperty(name, v); }
    return e;
  }

  function cut(v, n) {
    var t = (v === undefined || v === null) ? '' : String(v);
    return t.length > n ? t.slice(0, n) + '…' : t;
  }

  function ratio(a, b) {
    return (b > 0 ? Math.round(a / b * 100) : 0) + '%';
  }

  function dot(color) {
    return cssVar(el('i', 'skd-dot'), '--skd-c', hex(color));
  }

  function kicker(card, color, s) {
    var k = add(card, 'div', 'skd-card__kicker');
    k.appendChild(dot(color));
    return text(k, s);
  }

  function statRow(card) {
    return add(card, 'div', 'skd-card__stats');
  }

  function stat(st, num, label) {
    var sp = add(st, 'span');
    add(sp, 'b', null, num);
    return text(sp, label);
  }

  function castRow(parent, list, max) {
    var arr = list || [];
    var box = add(parent, 'div', 'skd-cast');
    var chip, i, n = Math.min(arr.length, max);
    for (i = 0; i < n; i++) {
      chip = add(box, 'span', 'skd-cast__chip');
      chip.appendChild(dot(arr[i] && arr[i].color));
      text(chip, arr[i] && arr[i].name);
    }
    if (arr.length > max) { add(box, 'span', 'skd-cast__more', '等 ' + arr.length + ' 人'); }
    return box;
  }

  function root(kind) {
    return el('div', 'skd-card skd-card--' + kind);
  }

  /* 星体卡：点 + 组名·身份 + rank / 名字 / 身份摘要 / 事件·联系 / 进入罗盘提示 */
  function star(o) {
    o = o || {};
    var card = root('star');
    var k = kicker(card, o.color, (o.camp || '') + ' · ' + (o.role || ''));
    if (o.rank) { add(k, 'b', 'skd-card__mag', o.rank); }
    add(card, 'div', 'skd-card__title', o.name);
    add(card, 'div', 'skd-card__sub', cut(o.identity, 40));
    var st = statRow(card);
    stat(st, o.events || 0, ' 事件');
    stat(st, o.relations || 0, ' 联系');
    add(card, 'div', 'skd-card__hint', '点击进入罗盘');
    return card;
  }

  /* 阵营卡：成员前列 + 立场构成条 + 组内/组外关系数 */
  function camp(o) {
    o = o || {};
    var card = root('camp');
    kicker(card, o.color, (o.label || '') + ' · ' + (o.count || 0) + ' 人');
    add(card, 'div', 'skd-card__title', o.name);

    var list = o.members || [];
    var ol = add(card, 'ol', 'skd-card__members');
    var i, li;
    for (i = 0; i < Math.min(list.length, 5); i++) {
      li = add(ol, 'li', i === 0 ? 'is-lead' : null, list[i]);
    }

    var bars = add(card, 'div', 'skd-bars');
    var cls = o.classes || [];
    var total = list.length;
    var row, fill;
    for (i = 0; i < cls.length; i++) {
      row = add(bars, 'div', 'skd-bar');
      add(row, 'span', 'skd-bar__label', cls[i].label);
      fill = add(row, 'i', 'skd-bar__fill');
      cssVar(fill, '--skd-w', ratio(cls[i].count || 0, total));
      cssVar(fill, '--skd-c', hex(cls[i].color));
      add(row, 'b', null, cls[i].count || 0);
    }

    var st = statRow(card);
    stat(st, o.inner || 0, ' 组内');
    stat(st, o.outer || 0, ' 组间');
    return card;
  }

  /* 线索卡：所属段 / 归纳来源 / 回次跨度 / 出场者 / 收束悬置 */
  function line(o) {
    o = o || {};
    var card = root('line');
    var head = (KIND[o.kind] || o.kind || '') + (o.theme ? '' : '');
    if (o.kind !== 'main' && o.mainLabel) { head += ' · 属「' + o.mainLabel + '」段'; }
    if (o.derived) { head += ' · 算法归纳'; }
    kicker(card, o.color, head);

    var t = add(card, 'div', 'skd-card__title', o.label);
    if (o.theme) { add(t, 'small', null, o.theme); }

    var wrap = add(card, 'div', 'skd-span');
    var track = add(wrap, 'i', 'skd-span__track');
    var fill = add(track, 'i', 'skd-span__fill');
    var nCh = o.nCh || 0;
    cssVar(fill, '--skd-a0', ratio(o.c0 || 0, nCh));
    cssVar(fill, '--skd-a1', ratio((o.c1 || 0) + 1, nCh));
    cssVar(fill, '--skd-c', hex(o.color));
    add(wrap, 'span', 'skd-span__txt',
      '第 ' + o.no0 + (o.no0 === o.no1 ? '' : '–' + o.no1) + ' ' + (o.unit || '回') + ' · ' + o.span +
      ' ' + (o.unit || '回') + ' · ' + o.events + ' 事件 · ' + (o.cast ? o.cast.length : 0) + ' 人');

    castRow(card, o.cast, 10);

    if (o.resolved || o.suspended) {
      add(card, 'div', 'skd-card__foot', o.resolved ? '收束' : '悬置');
    }
    return card;
  }

  /* 事件卡：回次眉题 / 标题 / 摘要 / 出场者 */
  function event(o) {
    o = o || {};
    var card = root('event');
    var head = '第 ' + o.no + ' ' + (o.unit || '回') + ' · ';
    if (o.count > 1) {
      head += o.count + ' 个事件';
      if (o.keyCount > 0) { head += ' · ' + o.keyCount + ' 关键'; }
    } else {
      head += (o.kind || '');
    }
    add(card, 'div', 'skd-card__kicker', head);
    add(card, 'div', 'skd-card__title', o.title);
    add(card, 'div', 'skd-card__body', o.summary);
    castRow(card, o.cast, 8);
    return card;
  }

  /* 证据卡：档案号眉题 / 评分或待建档 / 依据 / 原文摘录 */
  function evidence(o) {
    o = o || {};
    var card = root('evidence');
    add(card, 'div', 'skd-card__kicker', o.key + ' · ' + (o.en || ''));
    var t = add(card, 'div', 'skd-card__title',
      o.pending ? '待建档' : (o.score || 0) + ' / 100');
    if (o.low) { add(t, 'small', null, '证据不足'); }
    add(card, 'div', 'skd-card__body', o.basis);
    var ev = o.evidence || [];
    var ul = add(card, 'ul', 'skd-card__quotes');
    var i, n = Math.min(ev.length, 3);
    for (i = 0; i < n; i++) { add(ul, 'li', null, cut(ev[i], 60)); }
    return card;
  }

  function mount(host, node) {
    if (!host) { return false; }
    while (host.firstChild) { host.removeChild(host.firstChild); }
    if (node) { host.appendChild(node); }
    return true;
  }

  g.CLSkyCards = {
    star: star,
    camp: camp,
    line: line,
    event: event,
    evidence: evidence,
    mount: mount
  };
})(window);
