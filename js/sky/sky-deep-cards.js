/*!
 * @role deepcards
 * @owns js/sky/sky-deep-cards.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 * 光层信息卡与星/团悬停接线。宿主 getter 每次读当前状态，指针对象与帧循环同源。
 * 无自有帧循环；数据与分组色来自宿主，不复制换书前的图谱或光层实例。
 */
(function (g) {
  'use strict';
  function create(o) {
    var doc = g.document, cardEl = null, cardKind = null, pointer = o.pointer;
  /* ── 罗盘轴签证据卡：悬停 / 聚焦属性轴签 → 分数、依据、原文证据；叙事轴 → 定义 ─────── */
  function axisCard(lab) {
    var G = o.graph();
    var key = lab.querySelector('.ln'), en = lab.querySelector('.le'), c = null, name = CLSky && CLSky.state ? CLSky.state().compass : null;
    if (!key || !name) return null;
    key = key.textContent.trim();
    c = G.characters.filter(function (x) { return x.name === name; })[0];
    if (lab.classList.contains('attr')) {
      var a = c && c.attrs ? c.attrs[key] : null;
      return CLSkyCards.evidence({ key: key, en: en ? en.textContent : '', score: a && a.score != null ? a.score : null, low: !!(a && a.low), pending: !a || a.score == null || !!a.pending,
        basis: a ? a.basis || '' : '材料里没有这一维的依据', evidence: a && a.evidence ? a.evidence : [] });
    }
    var DEF = (g.CLScene && CLScene.META_DEF) || {}, lv = lab.querySelector('.lv');
    return CLSkyCards.evidence({ key: key, en: en ? en.textContent : '', score: lv ? +lv.textContent : null, low: false, pending: !lv, basis: DEF[key] || '叙事维度：由事件与关系推算', evidence: [] });
  }
  function onAxisOver(e) {
    if (!o.enabled() || o.mode() !== 'compass' || !e.target.closest) return;
    var lab = e.target.closest('#labels .cl-lab.attr, #labels .cl-lab.meta'); if (!lab) return;
    var node = axisCard(lab); if (!node) return;
    var r = lab.getBoundingClientRect(); pointer.x = r.right; pointer.y = r.top;
    showNode('axis', node);
  }
  function onAxisOut(e) {
    if (cardKind !== 'axis' || !e.target.closest) return;
    var lab = e.target.closest('#labels .cl-lab.attr, #labels .cl-lab.meta'), to = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('#labels .cl-lab.attr, #labels .cl-lab.meta') : null;
    if (lab && lab !== to) hideCard();
  }

  /* ── 卡片（星 / 团；线卡由 sky-shell 调 lineCard） ─────── */
  function hideCard() { if (cardEl && cardKind) { cardEl.hidden = true; cardKind = null; } }
  function placeCard(x, y) {
    var W = g.innerWidth, H = g.innerHeight, w = cardEl.offsetWidth || 260, h = cardEl.offsetHeight || 120, left = x + 18, top = y + 16;
    if (left + w > W - 12) left = x - w - 18;
    if (top + h > H - 96) top = y - h - 16;
    cardEl.classList.toggle('is-dock', false);
    cardEl.style.setProperty('--sc-x', Math.max(12, left).toFixed(0) + 'px');
    cardEl.style.setProperty('--sc-y', Math.max(72, top).toFixed(0) + 'px');
  }
  function showNode(kind, node) { if (!cardEl || !node) return; CLSkyCards.mount(cardEl, node); cardEl.hidden = false; cardKind = kind; placeCard(pointer.x, pointer.y); }
  function starCard(name) {
    var G = o.graph(), S = o.scene(), evCount = o.events(), relCount = o.relations();
    var c = G.characters.filter(function (x) { return x.name === name; })[0], n = S.nodeOf('c:' + name); if (!c || !n) return null;
    return CLSkyCards.star({ name: name, identity: c.identity || c.brief || '', role: c.role || '', camp: n.camp || '散星', stance: c.stance || '',
      color: o.color(o.info(), n.camp), rank: n.bayer || '', events: evCount[name] || 0, relations: relCount[name] || 0 });
  }
  function campCard(s) {
    var S = o.scene(), G = o.graph(), T = o.tokens(), app = o.app();
    var cps = S.camps ? S.camps() : [], cp = cps.filter(function (x) { return x.name === s.name; })[0] || { members: [] };
    var set = {}; cp.members.forEach(function (m) { set[m] = 1; });
    var V = app.atlas && app.atlas.skyView ? app.atlas.skyView() : G, inner = 0, outer = 0, cls = {}, DM = g.CLDomainsModel;
    (V.relations || []).forEach(function (r) {
      var ia = !!set[r.a], ib = !!set[r.b]; if (!ia && !ib) return;
      if (ia && ib) inner++; else outer++;
      var rc = DM && DM.relClass ? DM.relClass(r) : null, id = rc ? rc.id : 'other';
      if (!cls[id]) cls[id] = { label: rc ? rc.label : '联系', count: 0, color: rc ? rc.hex : T.C.INK3 };
      cls[id].count++;
    });
    var list = Object.keys(cls).map(function (k) { return cls[k]; }).sort(function (a, b) { return b.count - a.count; }).slice(0, 5);
    var lab = doc.querySelector('#skyGroup [aria-checked="true"]');
    return CLSkyCards.camp({ name: s.name, color: s.color, label: lab ? lab.textContent : '阵营', count: s.count, members: cp.members.slice(0, 5), inner: inner, outer: outer, classes: list });
  }
  function lineCard(info) {
    var M = o.model(), S = o.scene(), T = o.tokens();
    if (!o.enabled() || !g.CLSkyCards || !info) return null;
    var info2 = o.info();
    return CLSkyCards.line({ kind: info.kind, label: info.label, theme: info.theme, mainLabel: info.mainLabel, derived: info.derived, no0: info.no0, no1: info.no1,
      span: info.span, events: info.events, unit: M && M.axis ? M.axis.unit : '回',
      cast: (info.cast || []).map(function (nm) { var n = S.nodeOf('c:' + nm); return { name: nm, color: o.color(info2, n ? n.camp : '') }; }),
      c0: info.c0, c1: info.c1, nCh: M ? M.nCh : 1, resolved: info.resolved, suspended: info.suspended, color: T.GEN[(info.gen | 0) % T.GEN.length] });
  }
  /* quiet：牵引拖动中只点亮一跳网络、不弹星卡（已显示的星卡一并收起），sky-tug-fx 走这条 */
  function onStarHover(e, quiet) {
    var S = o.scene(), stars = o.stars(), bun = o.bundles(), hoverStar, hotCamp = o.hotCamp();
    if (!o.enabled()) return;
    hoverStar = e && e.name ? e.name : null; o.setHoverStar(hoverStar);
    /* 拖星的 quiet 路径没有经过 scene 的 DOM 命中层；同步场景巡礼，
       让隐藏的关系纤维也按同一颗星的一跳范围亮起。 */
    if (S.setHover) S.setHover(hoverStar);
    stars.setHover(hoverStar);
    if (o.mode() !== 'constellation') return;
    bun.emphasize(hoverStar ? { star: hoverStar, group: -1 } : { group: hotCamp != null ? hotCamp : -1, star: null });
    /* 焦点 + 语境：一跳网络保持全亮，其余星压暗；离开后回到团悬停或全亮 */
    stars.setLit(hoverStar ? o.hop(hoverStar) : hotMembers());
    if (hoverStar && !quiet) showNode('star', starCard(hoverStar)); else if (cardKind === 'star') hideCard();
  }
  function hotMembers() {
    var S = o.scene(), hotCamp = o.hotCamp();
    if (hotCamp == null) return null;
    var info = o.info(), s = info && info.sectors[hotCamp], cps = S.camps ? S.camps() : [], cp = s ? cps.filter(function (x) { return x.name === s.name; })[0] : null;
    return cp && cp.members && cp.members.length ? cp.members.slice() : null;
  }
  /* quiet：分组卡片叠自己就在手边，不再弹浮动团卡 */
  function onCampHover(s, quiet) {
    var neb = o.nebula(), bun = o.bundles(), stars = o.stars(), hoverStar = o.hoverStar(), hotCamp;
    if (!o.enabled() || o.mode() !== 'constellation') return;
    var info = o.info(); hotCamp = s ? o.sectorIndex(info, s.name) : null; o.setHotCamp(hotCamp);
    neb.hover(hotCamp != null ? hotCamp : -1);
    bun.emphasize({ group: hotCamp != null ? hotCamp : -1, star: null });
    if (!hoverStar) stars.setLit(hotMembers());
    if (s && !quiet) showNode('camp', campCard(s)); else if (cardKind === 'camp') hideCard();
  }

    function onMove(e) {
      pointer.x = e.clientX; pointer.y = e.clientY;
      if (cardKind && cardEl && !cardEl.hidden) placeCard(pointer.x, pointer.y);
    }
    return { setElement: function (el) { cardEl = el; }, kind: function () { return cardKind; },
      hide: hideCard, line: lineCard, hoverStar: onStarHover, hoverCamp: onCampHover,
      axisOver: onAxisOver, axisOut: onAxisOut, move: onMove };
  }
  g.CLSkyDeepCards = { create: create };
})(window);
