/* Castline · tree-gate.js — v32 挂在树上的「显示剧情线」按钮（window.CLTreeGate）
 *
 * 巨树本身不可点击（背景层、raycast 全置空），所以能点的只有这一枚挂在树干上的牌子。
 * 它只发 cl:tree-plotline 事件，不亲自搬星点 —— 搬星点是 CLStarMigrate 的事，
 * 这样按钮、迁移、取景三件才能各自单独测。
 */
(function () {
  'use strict';

  var ID = 'clTreeGate', CSS_ID = 'clTreeGateCss';
  var ANCHORS = [0.34, 0.52, 0.68];       // 撞面板就依次往上挪
  var EVERY = 3;                          // 每 3 帧更新位置（每帧算投影太贵）
  var HUD_SEL = '.panel,#ops,#viewbar,#dock';

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  var el = null, styleEl = null, state = 'stars', mounted = false, muted = false;
  var frame = 0, lastX = 0, lastY = 0, anchorT = ANCHORS[0], onK = 1, selfFire = false;
  var reduce = false, boxes = [], boxAt = 0, vis = false, handler = null, shown = true;

  function css() {
    if (document.getElementById(CSS_ID)) return;
    styleEl = document.createElement('style');
    styleEl.id = CSS_ID;
    // 只定义本层选择器。引线（::before）是关键：没有它这枚牌子会被读成又一个 HUD 按钮，
    // 而它要表达的是「这块牌子挂在那棵树上」。
    styleEl.textContent =
      '#' + ID + '{position:fixed;left:0;top:0;z-index:14;pointer-events:auto;cursor:pointer;' +
      'transform:translate(-9999px,-9999px);opacity:0;transition:opacity .3s,box-shadow .24s,border-color .24s;' +
      'padding:6px 12px;border-radius:3px;border:1px solid rgba(255,180,92,.34);' +
      'background:linear-gradient(180deg,rgba(10,7,20,.86),rgba(10,7,20,.62));' +
      '-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);' +
      'box-shadow:0 0 18px rgba(6,2,16,.7);white-space:nowrap;color:#efe6ff}' +
      '#' + ID + '.on{opacity:1}' +
      '#' + ID + ' b{display:block;font-size:13px;font-weight:600;letter-spacing:.06em;color:#efe6ff}' +
      '#' + ID + ' s{display:block;font-size:11px;text-decoration:none;letter-spacing:.12em;' +
      'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.72);margin-top:1px}' +
      '#' + ID + '::before{content:"";position:absolute;left:-13px;top:50%;width:12px;height:1px;' +
      'background:linear-gradient(270deg,rgba(255,180,92,.66),transparent)}' +
      '#' + ID + '::after{content:"";position:absolute;left:-16px;top:50%;width:4px;height:4px;' +
      'margin-top:-2px;border-radius:50%;background:rgba(255,180,92,.9);box-shadow:0 0 7px rgba(255,180,92,.8)}' +
      '#' + ID + ':hover{border-color:rgba(255,214,150,.72);box-shadow:0 0 24px rgba(255,180,92,.26),0 0 18px rgba(6,2,16,.7)}' +
      '#' + ID + '.act{border-color:rgba(255,214,150,.8);box-shadow:0 0 22px rgba(255,180,92,.22),0 0 18px rgba(6,2,16,.7)}' +
      '@media (prefers-reduced-motion:reduce){#' + ID + '{transition:none}}';
    document.head.appendChild(styleEl);
  }

  function story() {
    var s = (window.CLStory && CLStory.get) ? tryFn(CLStory.get) : null;
    return (s && s.ok) ? s : null;
  }
  function ghostReady() {
    var g = window.CLTreeGhost;
    if (!g || !g.stats) return false;
    var st = tryFn(g.stats);
    return !!(st && st.ready);
  }
  function anchor() {
    var A = window.CLTreeAnchor;
    return (A && A.toScreen && A.ready && tryFn(A.ready)) ? A : null;
  }

  function label() {
    if (!el) return;
    var t = story(), st = t ? t.stats : null;
    var b = el.children[0], s = el.children[1];
    if (state === 'plot') {
      b.textContent = '回到星座';
      var pl = null, m = window.CLStarMigrate;
      if (m && m.stats) { var ms = tryFn(m.stats); if (ms && typeof ms.placed === 'number') pl = ms.placed; }
      s.textContent = pl != null ? ('BACK TO STARS · ' + pl + ' 位') : 'BACK TO STARS';
    } else {
      b.textContent = '显示剧情线';
      // 副行两个数字只能取真值：取不到就整段不写，绝不编一个好看的数出来
      s.textContent = (st && typeof st.events === 'number' && typeof st.threads === 'number')
        ? ('PLOT LINES · ' + st.events + ' 点 · ' + st.threads + ' 线') : 'PLOT LINES';
    }
    el.classList.toggle('act', state === 'plot');
  }

  function mount() {
    if (mounted && el) return true;
    if (!document.body) return false;
    css();
    el = document.getElementById(ID);
    if (!el) {
      el = document.createElement('div');
      el.id = ID;
      el.innerHTML = '<b></b><s></s>';
      document.body.appendChild(el);
    }
    el.onclick = function (e) { if (e) e.stopPropagation(); API.toggle(); };
    mounted = true;
    label();
    return true;
  }

  function hudRects() {
    var now = Date.now();
    if (now - boxAt < 2000) return boxes;
    boxAt = now; boxes = [];
    try {
      Array.prototype.forEach.call(document.querySelectorAll(HUD_SEL), function (e2) {
        var r = e2.getBoundingClientRect();
        if (r.width > 4 && r.height > 4) boxes.push(r);
      });
    } catch (e3) {}
    return boxes;
  }

  function hit(x, y, w, h) {
    var bs = hudRects(), i;
    for (i = 0; i < bs.length; i++) {
      var b = bs[i];
      if (x < b.right && x + w > b.left && y < b.bottom && y + h > b.top) return true;
    }
    return false;
  }

  function place() {
    if (!el) return;
    var A = anchor();
    if (!A || !ghostReady() || !story() || !shown || muted || onK <= 0.01) {
      if (vis) { el.classList.remove('on'); vis = false; }
      return;
    }
    var w = el.offsetWidth || 130, h = el.offsetHeight || 34, i, got = null;
    for (i = 0; i < ANCHORS.length; i++) {
      var sc = A.toScreen([0, ANCHORS[i], 0]);
      if (!sc || !sc.on) continue;
      var x = sc.x + 16, y = sc.y - h * 0.5;
      if (!hit(x, y, w, h)) { got = { x: x, y: y, t: ANCHORS[i] }; break; }
      if (!got) got = { x: x, y: y, t: ANCHORS[i] };   // 全都撞就用第一个能投影出来的
    }
    if (!got) { if (vis) { el.classList.remove('on'); vis = false; } return; }
    anchorT = got.t;
    lastX = Math.round(got.x); lastY = Math.round(got.y);
    el.style.setProperty('--gx', lastX + 'px');
    el.style.setProperty('--gy', lastY + 'px');
    el.style.transform = 'translate(' + lastX + 'px,' + lastY + 'px)';
    if (!vis) { el.classList.add('on'); vis = true; }
  }

  var API = {
    name: 'tree-gate',
    build: function () {
      reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches);
      mount();
      // dispose 会摘监听，而秘仪层每次重建布局都走 dispose→build。不在这里补挂就再也同步不上外部切换。
      if (!handler) {
        handler = function (ev) {
          if (selfFire) return;                       // 自己发的那次不再自触发，防死循环
          var d = ev && ev.detail;
          if (d && d.on === true) state = 'plot';
          else if (d && d.on === false) state = 'stars';
          label();
        };
        try { document.addEventListener('cl:tree-plotline', handler); } catch (e) {}
      }
      place();
      return API.stats();
    },
    update: function (s) {
      s = s || {};
      onK = num(s.on, 1);
      if (!mounted) { if ((++frame % 30) === 0) mount(); return; }
      if ((++frame % EVERY) === 0) place();
      if ((frame % 60) === 0) label();               // placed 会变，副行跟着走
    },
    dispose: function () {
      try { if (handler) document.removeEventListener('cl:tree-plotline', handler); } catch (e) {}
      handler = null;
      if (el && el.parentNode) el.parentNode.removeChild(el);
      if (styleEl && styleEl.parentNode) styleEl.parentNode.removeChild(styleEl);
      el = null; styleEl = null; mounted = false; vis = false;
    },
    setOn: function (v) { muted = !v; place(); },
    toggle: function () { return API.setState(state === 'plot' ? 'stars' : 'plot'); },
    setState: function (v) {
      var next = (v === 'plot' || v === true) ? 'plot' : 'stars';
      if (next === state) { label(); return state; }
      state = next;
      label();
      selfFire = true;
      try { document.dispatchEvent(new CustomEvent('cl:tree-plotline', { detail: { on: state === 'plot' } })); }
      catch (e) {}
      selfFire = false;
      return state;
    },
    state: function () { return state; },
    show: function (v) { shown = v !== false; place(); },
    visible: function () { return vis; },
    stats: function () {
      var t = story(), st = t ? t.stats : null;
      return { mounted: mounted, visible: vis, state: state, x: lastX, y: lastY, anchorT: anchorT,
        hasAnchor: !!anchor(), hasGhost: ghostReady(),
        events: st ? num(st.events, 0) : 0, threads: st ? num(st.threads, 0) : 0, muted: muted };
    }
  };

  window.CLTreeGate = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
