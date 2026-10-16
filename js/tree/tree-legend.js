(function () {
  'use strict';

  var ID = 'clTreeLegend', CSS_ID = 'clTreeLegendCss';
  var EVERY = 3;
  var ANCHOR_Y = 0.86;
  var Y_TOL = 0.14;
  var GAP = 20;
  var HUD_SEL = '.panel,#ops,#viewbar,#dock,#clTreeMarks .m.on';
  var NUDGE = [0, -74, 74, -148];

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  var el = null, styleEl = null, mounted = false, muted = false, vis = false, shown = true;
  var frame = 0, lastKey = '';
  var focusKind = null;
  var st = { mounted: false, visible: false, kinds: 0, total: 0, anchor: null, rows: [] };

  function css() {
    if (document.getElementById(CSS_ID)) return;
    styleEl = document.createElement('style');
    styleEl.id = CSS_ID;
    styleEl.textContent =
      '#' + ID + '{position:fixed;left:0;top:0;z-index:12;pointer-events:none;' +
      'transform:translate(-9999px,-9999px);opacity:0;transition:opacity .35s;' +
      'padding:7px 11px 7px 12px;border-radius:3px;border:1px solid rgba(255,180,92,.26);' +
      'background:linear-gradient(180deg,rgba(10,7,20,.84),rgba(10,7,20,.58));' +
      '-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);' +
      'box-shadow:0 0 18px rgba(6,2,16,.68);white-space:nowrap;color:#efe6ff}' +
      '#' + ID + '.on{opacity:1}' +
      '#' + ID + '::before{content:"";position:absolute;left:-' + GAP + 'px;top:22px;width:' + (GAP - 1) + 'px;height:1px;' +
      'background:linear-gradient(270deg,rgba(255,180,92,.54),rgba(255,180,92,.10))}' +
      '#' + ID + '::after{content:"";position:absolute;left:-' + (GAP + 3) + 'px;top:20px;width:4px;height:4px;' +
      'border-radius:50%;background:rgba(255,180,92,.85);box-shadow:0 0 7px rgba(255,180,92,.75)}' +
      '#' + ID + ' .h{font-size:11px;letter-spacing:.16em;' +
      'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.6);margin-bottom:5px}' +
      '#' + ID + ' .r{display:flex;align-items:center;height:16px;cursor:pointer;pointer-events:auto;transition:all .3s ease}' +
      '#' + ID + ' .r.shrine{padding:1px 4px;margin:1px 0;border-radius:2px}' +
      '#' + ID + ' .r i{width:7px;height:7px;clip-path:polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%);margin-right:7px;flex:0 0 auto;transition:transform .3s ease,box-shadow .3s ease}' +
      '#' + ID + ' .r u{font-style:normal;text-decoration:none;font-size:11px;letter-spacing:.04em;' +
      'color:rgba(239,230,255,.88);width:30px}' +
      '#' + ID + ' .r v{font-style:normal;text-decoration:none;font-size:11px;min-width:24px;text-align:right;' +
      'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.62)}' +
      '#' + ID + ' .r.z u,#' + ID + ' .r.z v{opacity:.42}' +
      '#' + ID + ' .r em{font-style:normal;display:block;height:5px;margin-left:8px;border-radius:2px;' +
      'background:currentColor;opacity:.5}' +
      '#' + ID + ' .r.on{background:rgba(255,180,92,.16);box-shadow:inset 0 0 0 1px rgba(255,180,92,.65),0 0 10px rgba(255,180,92,.35);border-radius:2px;transform:translateY(-1px)}' +
      '#' + ID + ' .r.on i{transform:scale(1.25);box-shadow:0 0 10px currentColor}' +
      '#' + ID + ' .r.on u{color:#fff}' +
      '#' + ID + ' .r.dimmed{opacity:.42}' +
      /* v38：hover 仅微亮，比 .on 更淡 */
      '#' + ID + ' .r:hover{background:rgba(255,180,92,.055);border-radius:2px}' +
      '@media (prefers-reduced-motion:reduce){#' + ID + '{transition:none}}';
    document.head.appendChild(styleEl);
  }

  function build() {
    if (mounted) return true;
    if (!document.body) return false;
    css();
    el = document.createElement('div');
    el.id = ID;
    document.body.appendChild(el);
    el.addEventListener('click', onClick, false);
    mounted = true;
    st.mounted = true;
    return true;
  }

  function anchorPoint(shape) {
    if (!shape) return null;
    var best = null, bestR = -1, i, j;
    function scan(list) {
      for (i = 0; i < (list || []).length; i++) {
        var p = list[i] && list[i].pts;
        if (!p) continue;
        for (j = 0; j < p.length; j++) {
          var q = p[j];
          if (!q) continue;
          if (Math.abs(q[1] - ANCHOR_Y) > Y_TOL) continue;
          var r = Math.sqrt(q[0] * q[0] + q[2] * q[2]);
          if (q[0] <= 0) continue;
          if (r > bestR) { bestR = r; best = q; }
        }
      }
    }
    scan(shape.boughs); scan(shape.limbs); scan(shape.twigs);
    if (!best && shape.trunk && shape.trunk.pts) {
      var tp = shape.trunk.pts, k = 0;
      for (i = 0; i < tp.length; i++) if (Math.abs(tp[i][1] - ANCHOR_Y) < Math.abs(tp[k][1] - ANCHOR_Y)) k = i;
      best = tp[k];
    }
    return best;
  }

  function tally(shape) {
    var P = window.CLPalette;
    var KINDS = (P && P.KINDS) ? P.KINDS : ['高燃', '转折', '抉择', '冲突', '关系', '领悟', '日常'];
    var CSS = (P && P.CSS) ? P.CSS : ['#ffd166', '#ffb45c', '#c8a7ff', '#ff5d73', '#ff9ad5', '#7af0c8', '#9a92b8'];
    var cnt = {}, i, k;
    for (i = 0; i < KINDS.length; i++) cnt[KINDS[i]] = 0;
    var tw = (shape && shape.twigs) || [];
    var total = 0;
    for (i = 0; i < tw.length; i++) {
      k = tw[i] && tw[i].kind;
      if (k == null || cnt[k] === undefined) k = '日常';
      cnt[k]++; total++;
    }
    var rows = [];
    for (i = 0; i < KINDS.length; i++) rows.push({ kind: KINDS[i], css: CSS[i], count: cnt[KINDS[i]] });
    return { rows: rows, total: total };
  }

  function render(t) {
    if (!el) return;
    var key = t.total + '|' + t.rows.map(function (r) { return r.count; }).join(',');
    if (key === lastKey) return;
    lastKey = key;
    var h = ['<div class="h">事件类型 · ' + t.total + '</div>'];
    for (var i = 0; i < t.rows.length; i++) {
      var r = t.rows[i];
      h.push('<div class="r shrine' + (r.count ? '' : ' z') + '">' +
        '<i style="background:' + r.css + ';color:' + r.css + ';box-shadow:0 0 7px ' + r.css + '"></i>' +
        '<u>' + r.kind + '</u><v>' + r.count + '</v></div>');
    }
    el.innerHTML = h.join('');
  }

  function overlaps(x, y, w, hh) {
    var boxes = document.querySelectorAll(HUD_SEL), i;
    for (i = 0; i < boxes.length; i++) {
      var b = boxes[i].getBoundingClientRect();
      if (!b.width || !b.height) continue;
      if (x < b.right + 8 && x + w > b.left - 8 && y < b.bottom + 8 && y + hh > b.top - 8) return true;
    }
    return false;
  }

  function place() {
    if (!el || !vis) return;
    var A = window.CLTreeAnchor;
    if (!A || !A.toScreen) return;
    var p = st.anchor;
    if (!p) return;
    var S = window.CLTreeSway;
    var q = (S && S.bend) ? tryFn(function () { return S.bend(p); }) : null;
    if (!q) q = p;
    var s = tryFn(function () { return A.toScreen(q); });
    if (!s || !s.on) { el.classList.remove('on'); return; }
    var w = el.offsetWidth || 96, hh = el.offsetHeight || 140;
    var x = s.x + GAP + 6, y = s.y - 22, i;
    for (i = 0; i < NUDGE.length; i++) {
      if (!overlaps(x, y + NUDGE[i], w, hh)) { y += NUDGE[i]; break; }
    }
    var vw = window.innerWidth || 1400, vh = window.innerHeight || 900, LM = 8, lead = GAP + 3;
    x = Math.max(LM + lead, Math.min(x, vw - w - LM));
    y = Math.max(LM, Math.min(y, vh - hh - LM));
    el.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
    el.classList.add('on');
    st.x = Math.round(x); st.y = Math.round(y);
  }

  function treeShown() {
    var g = window.CLTreeGhost;
    if (!g || !g.stats) return false;
    var gs = tryFn(g.stats);
    if (!gs || !gs.ready) return false;
    var S = window.CLTreeStage;
    var ss = (S && S.stats) ? tryFn(S.stats) : null;
    return !!(ss && ss.active);
  }

  function refresh() {
    var shape = (window.CLTreeGhost && CLTreeGhost.shapeOf) ? tryFn(CLTreeGhost.shapeOf) : null;
    if (!shape || !shape.trunk) { st.rows = []; st.kinds = 0; st.total = 0; return false; }
    var t = tally(shape);
    st.rows = t.rows; st.total = t.total;
    st.kinds = t.rows.length;
    st.anchor = anchorPoint(shape);
    render(t);
    applyFocus();
    return true;
  }

  /* v37 事件类型聚焦高亮：记录 + 把 .on 类打到匹配 kind 的那一行（沿用既有 .r 结构，不改顺序/类名序列）。 */
  function setFocus(kind) { focusKind = (kind == null || kind === '') ? null : kind; applyFocus(); }
  function applyFocus() {
    if (!el) return;
    var rows = el.querySelectorAll('.r'), i, u, isTarget;
    var hasFocus = !!focusKind;
    for (i = 0; i < rows.length; i++) {
      u = rows[i].querySelector('u');
      isTarget = hasFocus && u && u.textContent === focusKind;
      rows[i].classList.toggle('on', isTarget);
      rows[i].classList.toggle('dimmed', hasFocus && !isTarget);
    }
  }

  /* v38：图例行点击 → toggle 聚焦（事件委托挂在 el 上，innerHTML 重建不丢监听）。
   * 隐藏态防护：牌未 on 直接 return；未就绪守卫：CLTreeFocus 缺失静默 no-op；
   * ready=false 仍调用 set（记 pendingKind，设计如此）。同 kind 再点 = 取消（与键盘 1-7 一致）。 */
  function onClick(e) {
    /* v42 修（P1）：原门是 `el.classList.contains('on')` —— 那是**渲染态**，不是**可点态**。
     * 类要等 place() 成功才加上，而 place() 依赖锚点投影 + 让位试探；于是「树刚出现、
     * 牌子还没落位」的那一两帧里，行是看得见的、鼠标也是指针态，点击却被静默吞掉
     * （验收实测：先 Enter 无效、隔一帧再 Enter 才生效 —— 用户侧就是「第一下没反应」）。
     * 现在按本层自己的真相 vis 判（applyVis 维护，与 CSS 无关）：
     * 只要牌子该显示就接受点击；vis 为真但仍在 -9999 视线外的极端情况不会误伤 ——
     * 元素在视口外根本收不到真实点击。 */
    if (!el || !vis) return;
    var F = window.CLTreeFocus;
    if (!F || !F.get || !F.set) return;
    var row = (e.target && e.target.closest) ? e.target.closest('.r') : null;
    if (!row) {
      var n = e.target;
      while (n && n !== el && !(n.classList && n.classList.contains('r'))) n = n.parentNode;
      row = (n && n !== el) ? n : null;
    }
    if (!row) return;
    var u = row.querySelector ? row.querySelector('u') : null;
    var kind = u ? u.textContent : '';
    if (!kind) return;
    var cur = F.get() || {};
    var next = (cur.kind === kind) ? '' : kind;
    F.set(next);
  }

  function applyVis() {
    var want = shown && !muted && treeShown();
    vis = !!want;
    st.visible = vis;
    if (!el) return vis;
    if (!vis) el.classList.remove('on');
    else place();
    return vis;
  }

  function update(s) {
    frame++;
    if (!mounted && !build()) return;
    if (s && s.muted !== undefined) setOn(!s.muted);
    if (frame % EVERY === 0) {
      try { var g = window.CLTreeFocus && window.CLTreeFocus.get && window.CLTreeFocus.get(); focusKind = (g && g.kind) ? g.kind : null; }
      catch (e) { focusKind = null; }
    }
    if (frame % 30 === 1 || !st.rows.length) refresh();
    if (frame % EVERY === 0 || !vis) applyVis(); else place();
    applyFocus();
  }

  function setOn(v) { muted = !v; return applyVis(); }
  function show(v) { shown = (v == null) ? true : !!v; return applyVis(); }
  function visible() { return !!vis; }

  function stats() {
    return { mounted: mounted, visible: !!vis, muted: muted, shown: shown, focus: focusKind,
      kinds: st.kinds, total: st.total, anchor: st.anchor, x: st.x, y: st.y,
      rows: st.rows.map(function (r) { return { kind: r.kind, css: r.css, count: r.count }; }) };
  }

  var API = {
    name: 'tree-legend',
    build: function () { build(); refresh(); return stats(); },
    update: update,
    dispose: function () { if (el && el.parentNode) el.parentNode.removeChild(el); el = null; mounted = false; lastKey = ''; },
    setOn: setOn,
    show: show,
    visible: visible,
    refresh: refresh,
    setFocus: setFocus,
    stats: stats
  };
  window.CLTreeLegend = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  function boot() { build(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); hook(); }, false);
  } else { boot(); hook(); }
})();
