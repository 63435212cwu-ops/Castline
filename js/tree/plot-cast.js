/* Castline · plot-cast.js — v32 枝上角色显名（window.CLPlotCast）
 *
 * 星点飞到枝干上之后还缺一件：名字。没有名字，那就只是一堆光点。
 * 用户的原话是「每个支干上要有**有角色参与或者出场的显示**」——所以这一层做两件事：
 *   ① 每根一级枝、每个主干段各显一个主导角色名；
 *   ② 区分「参与」（在这条线上有 ≥2 个剧情点）与「出场」（只露一面）——实心点 / 空心圈 + 文字标注，
 *      不靠颜色也能读。
 *
 * 只在剧情线模式下显示：星座态显名字会和角色姓名标签打架。
 */
(function () {
  'use strict';

  var LAB_ID = 'clPlotCastLab', CSS_ID = 'clPlotCastCss';
  var MAX = 14, MAX_D1 = 8, EVERY = 4;
  var HUD_SEL = '.panel,#ops,#viewbar,#dock,#clTreeGate,#clTreeRead';
  var STAGE_SEL = '#ops,#clTreeGate,#clTreeRead';

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function str(v) { return v == null ? '' : String(v); }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }

  var layer = null, styleEl = null, items = [], frame = 0, deg = 0, onK = 1;
  var muted = false, shown = true, plotOn = false, handler = null, ready = false;
  var boxes = [], boxAt = 0, nShown = 0, nCand = 0, nDrop = 0, nLead = 0, sig = '';

  function css() {
    if (document.getElementById(CSS_ID)) return;
    styleEl = document.createElement('style');
    styleEl.id = CSS_ID;
    // 观感对齐仓里既有的 .cl-lab / .cl-plab：星图上的文字必须自带深底，否则被亮云吃掉。
    styleEl.textContent =
      '#' + LAB_ID + '{position:fixed;inset:0;pointer-events:none;z-index:12;overflow:hidden;contain:strict}' +
      '.cl-pcst{position:absolute;left:0;top:0;transform:translate(-9999px,-9999px);white-space:nowrap;' +
      'display:flex;flex-direction:column;gap:1px;padding-left:13px;margin-top:-9px;opacity:0;' +
      'transition:opacity .34s cubic-bezier(.16,1,.3,1);text-shadow:0 0 8px rgba(6,2,16,.92),0 0 2px #000}' +
      '.cl-pcst.on{opacity:1}' +
      '.cl-pcst::before{content:"";position:absolute;left:0;top:7px;width:10px;height:1px;opacity:.75;' +
      'background:linear-gradient(90deg,currentColor,transparent)}' +
      '.cl-pcst::after{content:"";position:absolute;left:-2px;top:5px;width:4px;height:4px;border-radius:50%;' +
      'background:currentColor;box-shadow:0 0 7px currentColor}' +
      '.cl-pcst b{font-size:12.5px;font-weight:600;letter-spacing:.05em;color:#efe6ff;' +
      'padding:1px 7px 1px 3px;margin-left:-3px;border-radius:2px;display:flex;align-items:center;gap:5px;' +
      'background:linear-gradient(90deg,rgba(8,6,16,.66),rgba(8,6,16,.30) 62%,rgba(8,6,16,0))}' +
      '.cl-pcst s{font-size:11px;text-decoration:none;letter-spacing:.10em;' +
      'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.72)}' +
      // 参与 = 实心，出场 = 空心：这两枚小记号是「参与还是只露一面」的唯一非文字线索
      '.cl-pcst i{width:4px;height:4px;border-radius:50%;display:inline-block;flex:0 0 auto}' +
      '.cl-pcst i.j{background:currentColor;box-shadow:0 0 6px currentColor}' +
      '.cl-pcst i.a{border:1px solid currentColor;background:none}' +
      '.cl-pcst.lf{padding-left:0;padding-right:13px;align-items:flex-end}' +
      '.cl-pcst.lf::before{left:auto;right:0;background:linear-gradient(270deg,currentColor,transparent)}' +
      '.cl-pcst.lf::after{left:auto;right:-2px}' +
      '.cl-pcst.lf b{margin-left:0;margin-right:-3px;padding:1px 3px 1px 7px;flex-direction:row-reverse;' +
      'background:linear-gradient(270deg,rgba(8,6,16,.66),rgba(8,6,16,.30) 62%,rgba(8,6,16,0))}' +
      '@media (prefers-reduced-motion:reduce){.cl-pcst{transition:none}}';
    document.head.appendChild(styleEl);
  }

  function anchor() {
    var A = window.CLTreeAnchor;
    return (A && A.toScreen && A.ready && tryFn(A.ready)) ? A : null;
  }
  function storyTree() {
    var t = (window.CLStory && CLStory.get) ? tryFn(CLStory.get) : null;
    return (t && t.ok) ? t : null;
  }
  function shapeNow() {
    var t = storyTree();
    if (!t || !window.CLTreeShape || !CLTreeShape.build) return null;
    var s = tryFn(function () { return CLTreeShape.build(t); });
    return (s && s.ok) ? s : null;
  }
  function migPlot() {
    var m = window.CLStarMigrate;
    if (!m || !m.state) return false;
    var st = tryFn(m.state);
    return st === 'plot' || st === 'flying';
  }

  /** 候选清单：主干段优先，其次一级枝按线长降序。
   *  名字一律取真值（thread.lead → cast[0].name），两个都空就跳过 —— 不许编。 */
  function collect() {
    var s = shapeNow(), t = storyTree();
    if (!s || !t) return [];
    var TH = t.threads || [], byId = {}, i, j, out = [];
    for (i = 0; i < TH.length; i++) byId[str(TH[i].id)] = TH[i];

    var segs = (t.trunk && t.trunk.segments) || [], sp = s.trunk.pts, sr = s.trunk.r;
    for (i = 0; i < segs.length; i++) {
      var sg = segs[i], th0 = byId[str(sg.threadId)];
      var nm0 = str(sg.lead) || (th0 && str(th0.lead)) || (th0 && th0.cast && th0.cast[0] ? str(th0.cast[0].name) : '');
      if (!nm0) continue;
      var mt = (num(sg.t0, 0) + num(sg.t1, 1)) * 0.5;
      var hi = Math.max(0, Math.min(sp.length - 1, Math.round(mt * (sp.length - 1))));
      var p = sp[hi], off = num(sr[hi], 0.01) * 3.2 + 0.045;
      out.push({ pri: 0, name: nm0, pos: [p[0] + off, p[1], p[2]],
        sub: '主干 · 第 ' + (i + 1) + ' 段', n: castN(th0, nm0), col: colOf(num(sg.color, 0xffb45c)),
        len: th0 ? num(th0.len, 0) : 0 });
    }

    var bs = s.boughs || [];
    for (i = 0; i < bs.length; i++) {
      var b = bs[i], th = byId[str(b.threadId)];
      var nm = str(b.lead) || (th && str(th.lead)) || (th && th.cast && th.cast[0] ? str(th.cast[0].name) : '');
      if (!nm) continue;
      var pts = b.pts, k = Math.max(0, Math.min(pts.length - 1, Math.round(pts.length * 0.62)));
      var cn = th && th.cast ? th.cast.length : 0, ln = th ? num(th.len, 0) : 0;
      out.push({ pri: 1, name: nm, pos: pts[k],
        sub: (cn ? cn + ' 人' : '') + (cn && ln ? ' · ' : '') + (ln ? ln + ' 点' : ''),
        n: castN(th, nm), col: colOf(num(b.color, 0xffb45c)), len: ln });
    }
    out.sort(function (a, b2) { return a.pri - b2.pri || b2.len - a.len || (a.name < b2.name ? -1 : 1); });
    return out;
  }

  function castN(th, nm) {
    if (!th || !th.cast) return 0;
    for (var i = 0; i < th.cast.length; i++) if (str(th.cast[i].name) === nm) return num(th.cast[i].n, 0);
    return 0;
  }
  function colOf(hex) {
    var r = (hex >> 16) & 255, g = (hex >> 8) & 255, b = hex & 255;
    return 'rgb(' + Math.round(r * 0.55 + 120) + ',' + Math.round(g * 0.55 + 110) + ',' + Math.round(b * 0.55 + 140) + ')';
  }

  function rebuild() {
    css();
    if (!layer) {
      layer = document.getElementById(LAB_ID);
      if (!layer) {
        layer = document.createElement('div');
        layer.id = LAB_ID;
        layer.setAttribute('aria-hidden', 'true');
        document.body.appendChild(layer);
      }
    }
    var list = collect();
    nCand = list.length;
    var ns = list.length + '|' + (list[0] ? list[0].name : '');
    if (ns === sig && items.length) return items.length > 0;
    sig = ns;
    layer.innerHTML = '';
    items = [];
    for (var i = 0; i < list.length; i++) {
      var it = list[i], e = document.createElement('div');
      e.className = 'cl-pcst';
      e.style.color = it.col;
      // n>=2 记「参与」（推动了这条线），n===1 记「出场」（只露一面）
      var joined = it.n >= 2;
      e.innerHTML = '<b><i class="' + (joined ? 'j' : 'a') + '"></i><span></span></b><s></s>';
      e.querySelector('span').textContent = it.name;
      e.children[1].textContent = it.sub + (it.n ? (' · ' + (joined ? '参与' : '出场')) : '');
      layer.appendChild(e);
      items.push({ el: e, d: it, w: 0, h: 0, on: false });
    }
    ready = items.length > 0;
    return ready;
  }

  function hudRects() {
    var now = Date.now();
    if (now - boxAt < 2000) return boxes;
    boxAt = now; boxes = [];
    // 剧情线舞台里侧栏已被压到 22% 不透明度，再把它们当障碍会把中间一大片名字全避让掉
    // （实测 20 个候选只放下 4 个）。舞台态只避让仍然全亮的那几件。
    var sel = HUD_SEL;
    try { if (document.body && document.body.className.indexOf('cl-treestage') >= 0) sel = STAGE_SEL; } catch (e0) {}
    try {
      Array.prototype.forEach.call(document.querySelectorAll(sel), function (e2) {
        var r = e2.getBoundingClientRect();
        if (r.width > 4 && r.height > 4) boxes.push(r);
      });
    } catch (e3) {}
    return boxes;
  }

  function place() {
    if (!layer || !items.length) { nShown = 0; return; }
    var A = anchor();
    var live = shown && !muted && onK > 0.02 && (plotOn || migPlot());
    if (!A || !live) {
      for (var q = 0; q < items.length; q++) if (items[q].on) { items[q].el.classList.remove('on'); items[q].on = false; }
      nShown = 0; return;
    }
    var cap = deg >= 2 ? 99 : (deg >= 1 ? MAX_D1 : MAX);
    var W = window.innerWidth, H = window.innerHeight;
    var taken = hudRects().slice(), used = 0, drop = 0, lead = 0, i;
    for (i = 0; i < items.length; i++) {
      var it = items[i], e = it.el, ok = true;
      if (deg >= 2 && it.d.pri !== 0) ok = false;        // 重度降级只留主干段
      if (ok && used >= cap) { ok = false; drop++; }
      var sc = ok ? A.toScreen(it.d.pos) : null;
      if (ok && (!sc || !sc.on)) ok = false;
      if (ok) {
        if (!it.w) { var r0 = e.getBoundingClientRect(); it.w = Math.max(46, r0.width); it.h = Math.max(15, r0.height); }
        var flip = sc.x > W * 0.62;
        var bx = flip ? sc.x - it.w - 13 : sc.x, by = sc.y - it.h * 0.5;
        var box = { left: bx - 3, right: bx + it.w + 3, top: by - 2, bottom: by + it.h + 2 };
        for (var j = 0; j < taken.length; j++) {
          var t2 = taken[j];
          if (box.left < t2.right && box.right > t2.left && box.top < t2.bottom && box.bottom > t2.top) { ok = false; drop++; break; }
        }
        if (ok) {
          taken.push(box);
          e.classList.toggle('lf', flip);
          e.style.transform = 'translate(' + (flip ? sc.x - 13 - it.w : sc.x).toFixed(1) + 'px,' + by.toFixed(1) + 'px)';
          if (!it.on) { e.classList.add('on'); it.on = true; }
          used++; if (it.d.pri === 0) lead++;
          continue;
        }
      }
      if (it.on) { e.classList.remove('on'); it.on = false; }
    }
    nShown = used; nDrop = drop; nLead = lead;
  }

  var API = {
    name: 'plot-cast',
    build: function () {
      rebuild();
      // dispose 摘监听，而秘仪层每次重建布局都 dispose→build；不在这里补挂就再也收不到切换事件
      if (!handler) {
        handler = function (ev) {
          var d = ev && ev.detail;
          if (d && d.on === true) plotOn = true;
          else if (d && d.on === false) plotOn = false;
          place();
        };
        try { document.addEventListener('cl:tree-plotline', handler); } catch (e) {}
      }
      place();
      return API.stats();
    },
    update: function (s) {
      s = s || {};
      deg = num(s.degrade, 0);
      onK = num(s.on, 1);
      if (!ready) { if ((++frame % 30) === 0) rebuild(); return; }
      if ((++frame % EVERY) === 0) place();
    },
    dispose: function () {
      try { if (handler) document.removeEventListener('cl:tree-plotline', handler); } catch (e) {}
      handler = null;
      if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
      if (styleEl && styleEl.parentNode) styleEl.parentNode.removeChild(styleEl);
      layer = null; styleEl = null; items = []; ready = false; sig = ''; nShown = 0;
    },
    setOn: function (v) { muted = !v; place(); },
    rebuild: rebuild,
    show: function (v) { shown = v !== false; place(); },
    visible: function () { return nShown > 0; },
    stats: function () {
      return { ready: ready, on: +num(onK, 1).toFixed(3), shown: nShown, candidates: nCand,
        dropped: nDrop, lead: nLead, degrade: deg, muted: muted };
    }
  };

  window.CLPlotCast = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', hook); else hook();
})();
