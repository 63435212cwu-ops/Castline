(function () {
  'use strict';

  var ID = 'clTreeMarks', CSS_ID = 'clTreeMarksCss';
  var MAX_SEG = 3;
  var NEAR_PX = 90;
  var HUD_SEL = '.panel,#ops,#viewbar,#dock,#clTreeLegend,#clTreeGate';
  var NUDGE = [0, -20, 20, -40, 40, -62, 62];
  var EVERY = 3;
  var REFRESH = 30;
  var CASE_R = 0.86;

  function num(v, d) { v = +v; return isFinite(v) ? v : d; }
  function tryFn(f) { try { return f(); } catch (e) { return null; } }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }

  var el = null, styleEl = null, mounted = false, muted = false, shown = true;
  var vis = false, frame = 0;
  var mx = null, my = null;
  var slots = [];
  var near = null;
  var nameOf = {};
  var st = { mounted: false, visible: false, marks: 0, labels: 0, near: null, nearEv: 0, ringErr: null };

  function css() {
    if (document.getElementById(CSS_ID)) return;
    styleEl = document.createElement('style');
    styleEl.id = CSS_ID;
    styleEl.textContent =
      '#' + ID + '{position:fixed;left:0;top:0;width:0;height:0;z-index:11;pointer-events:none}' +
      '#' + ID + ' .m{position:absolute;left:0;top:0;padding:5px 9px 5px 10px;border-radius:3px;' +
      'border:1px solid rgba(255,180,92,.20);white-space:nowrap;opacity:0;' +
      '-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);' +
      'background:linear-gradient(180deg,rgba(10,7,20,.78),rgba(10,7,20,.52));' +
      'box-shadow:0 0 12px rgba(6,2,16,.55);transition:opacity .3s;' +
      'transform:translate(-9999px,-9999px)}' +
      '#' + ID + ' .m.on{opacity:1}' +
      '#' + ID + ' .m::before{content:"";position:absolute;left:-11px;top:50%;width:10px;height:1px;' +
      'background:linear-gradient(270deg,rgba(255,180,92,.5),transparent)}' +
      '#' + ID + ' .m::after{content:"";position:absolute;left:-14px;top:50%;width:4px;height:4px;' +
      'margin-top:-2px;border-radius:50%;background:rgba(255,180,92,.8);box-shadow:0 0 6px rgba(255,180,92,.7)}' +
      '#' + ID + ' .m b{display:block;font-size:12px;line-height:1.3;font-weight:600;letter-spacing:.03em;color:#efe6ff}' +
      '#' + ID + ' .m s{display:block;font-size:11px;text-decoration:none;letter-spacing:.12em;' +
      'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.68);margin-top:1px}' +
      '#' + ID + ' .m.k-ring{border-color:rgba(122,240,200,.24)}' +
      '#' + ID + ' .m.k-ring::after{background:rgba(122,240,200,.8);box-shadow:0 0 6px rgba(122,240,200,.7)}' +
      '#' + ID + ' .m.k-near{border-color:rgba(201,167,255,.32)}' +
      '#' + ID + ' .m.k-near::after{background:rgba(201,167,255,.9);box-shadow:0 0 8px rgba(201,167,255,.8)}' +
      '#' + ID + ' .m.k-seg{border-color:rgba(255,180,92,.28);box-shadow:0 0 14px rgba(255,180,92,.18)}' +
      '#' + ID + ' .tree-annual-ring{display:inline-flex;align-items:center;gap:4px;margin-bottom:2px}' +
      '#' + ID + ' .tree-annual-ring-svg{width:16px;height:16px;color:var(--arc-gold,#ffb45c);flex-shrink:0;overflow:visible}' +
      '#' + ID + ' .ring-outer-dots{transform-origin:11px 11px;animation:rdCoreSpin 24s linear infinite}' +
      '#' + ID + ' .ring-inner-numeral{transform-origin:11px 11px;animation:rdCoreSpin 36s linear reverse infinite}' +
      '#' + ID + ' .tree-ring-numeral{font-size:11px;color:var(--arc-gold,#ffb45c);font-family:var(--font-cjk-serif,serif);letter-spacing:.08em}' +
      '#' + ID + ' .m.flip::before{left:auto;right:-11px;background:linear-gradient(90deg,rgba(255,180,92,.5),transparent)}' +
      '#' + ID + ' .m.flip::after{left:auto;right:-14px;margin-top:-2px;background:rgba(255,180,92,.8);box-shadow:0 0 6px rgba(255,180,92,.7)}' +
      '@media (prefers-reduced-motion:reduce){#' + ID + ' .m{transition:none}}';
    document.head.appendChild(styleEl);
  }

  function build() {
    if (mounted) return true;
    if (!document.body) return false;
    css();
    el = document.createElement('div');
    el.id = ID;
    document.body.appendChild(el);
    mounted = true;
    st.mounted = true;
    return true;
  }

  function rings() {
    var v = window.CLTreeVeil;
    if (!v || !v.stats) return null;
    var s, err = null;
    try { s = v.stats(); } catch (e) { err = e; }
    if (!s) return null;
    st.ringErr = err ? String(err && err.message || err) : null;
    return (s && s.ringDef) ? s.ringDef : null;
  }


  function rebuildNames() {
    nameOf = {};
    var stO = window.CLStory;
    var t = (stO && stO.get) ? tryFn(stO.get) : null;
    if (!t || !t.threads) return;
    for (var i = 0; i < t.threads.length; i++) {
      var th = t.threads[i];
      if (!th) continue;
      nameOf[String(th.id)] = String(th.name || th.id);
    }
  }

  function trunkSegs() {
    var stO = window.CLStory;
    var t = (stO && stO.get) ? tryFn(stO.get) : null;
    if (!t || !t.threads) return null;
    var mains = [], i;
    for (i = 0; i < t.threads.length; i++) {
      var th = t.threads[i];
      if (th && th.kind === 'main') mains.push(th);
    }
    if (!mains.length) return null;
    mains.sort(function (a, b) { return (a.attach_order || 0) - (b.attach_order || 0); });
    var out = [];
    for (i = 0; i < mains.length && out.length < MAX_SEG; i++) {
      var m = mains[i];
      out.push({ name: String(m.name || m.id), events: (m.events || []).length, order: i, total: mains.length });
    }
    return out;
  }

  function ringAnchor(d, shape) {
    if (!shape) return [CASE_R, d.y, 0];
    var best = null, bestR = -1, i, j;
    function scan(list) {
      for (i = 0; i < (list || []).length; i++) {
        var p = list[i] && list[i].pts;
        if (!p) continue;
        for (j = 0; j < p.length; j++) {
          var q = p[j];
          if (!q) continue;
          if (Math.abs(q[1] - d.y) > 0.10) continue;
          var r = Math.sqrt(q[0] * q[0] + q[2] * q[2]);
          if (r > bestR) { bestR = r; best = q; }
        }
      }
    }
    scan(shape.boughs); scan(shape.limbs); scan(shape.twigs);
    if (!best) return [CASE_R, d.y, 0];
    return best;
  }

  function trunkAnchor(shape, frac) {
    var tp = shape && shape.trunk && shape.trunk.pts;
    if (!tp || !tp.length) return [0, frac, 0];
    var target = clamp(frac, 0, 1) * num(tp[tp.length - 1][1], 1);
    var best = null, bestD = 1e9, i;
    for (i = 0; i < tp.length; i++) {
      var dd = Math.abs(tp[i][1] - target);
      if (dd < bestD) { bestD = dd; best = tp[i]; }
    }
    return best || [0, frac, 0];
  }

  function nearestBranch(mx, my, shape) {
    var A = window.CLTreeAnchor;
    if (!A || !A.toScreen || !shape) return null;
    var best = null, bestD = 1e9;
    function scan(list) {
      for (var i = 0; i < (list || []).length; i++) {
        var b = list[i];
        if (!b || !b.pts) continue;
        for (var j = 0; j < b.pts.length; j += 2) {
          var pt = b.pts[j];
          var q = tryFn(function () { return A.toScreen(pt); });
          if (!q || !q.on) continue;
          var dx = q.x - mx, dy = q.y - my, dd = dx * dx + dy * dy;
          if (dd < bestD) { bestD = dd; best = { obj: b, d: Math.sqrt(dd) }; }
        }
      }
    }
    scan(shape.boughs);
    scan(shape.limbs);
    if (!best || best.d > NEAR_PX) return null;
    return best;
  }

  function eventsOn(obj, shape) {
    if (!shape || !shape.twigs || !obj) return 0;
    var n = 0, i;
    for (i = 0; i < shape.twigs.length; i++) {
      if (shape.twigs[i] && shape.twigs[i].host === obj.id) n++;
    }
    return n;
  }

  function tipOf(obj) {
    var p = obj && obj.pts;
    if (!p || !p.length) return [0, 0.5, 0];
    return p[p.length - 1];
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

  function eventsAtRing(dy, shape) {
    if (!shape || !shape.twigs) return 0;
    var n = 0, i;
    for (i = 0; i < shape.twigs.length; i++) {
      var w = shape.twigs[i];
      if (!w || !w.pts || !w.pts.length) continue;
      var tip = w.pts[w.pts.length - 1];
      if (Math.abs(tip[1] - dy) <= 0.06) n++;
    }
    return n;
  }

  function renderContent(shape) {
    if (!el) return;
    var want = [], i, si = 0;
    var rd = rings();
    if (rd) {
      for (i = 0; i < rd.length && i < 3; i++) {
        var d = rd[i], p = ringAnchor(d, shape);
        want.push({ key: 'ring' + i, kind: 'ring', dir: 1, flip: false, x: p[0], y: p[1], z: p[2],
          html: '<b>' + (num(d.y, 0) * 100).toFixed(0) + '% 树高</b><s>' +
            (d.dash ? '虚线环' : '刻度环') + ' · ' + eventsAtRing(num(d.y, 0), shape) + ' 事件</s>' });
      }
    }
    var segs = trunkSegs();
    if (segs) {
      for (i = 0; i < segs.length; i++) {
        var sg = segs[i];
        var frac = (sg.order + 0.5) / (segs.length || 1) * 0.78 + 0.11;
        var tp = trunkAnchor(shape, frac);
        var dir = (si % 2 === 0) ? 1 : -1; si++;
        var romanNumerals = ['卷一·潜渊', '卷二·裂变', '卷三·合流', '卷四·归墟', '卷五·通天'];
        var roman = romanNumerals[sg.order] || ('第 ' + (sg.order + 1) + ' 幕');
        var ringSvg = (window.CLAbyssRing && typeof window.CLAbyssRing.createSVGRuneRing === 'function')
          ? window.CLAbyssRing.createSVGRuneRing({ mini: true })
          : ('<svg class="tree-annual-ring-svg" width="16" height="16" viewBox="0 0 22 22">' +
             '<circle class="ring-outer-dots" cx="11" cy="11" r="9.5" fill="none" stroke="currentColor" stroke-width="0.8" stroke-dasharray="1.5 2.5"/>' +
             '<circle class="ring-inner-numeral" cx="11" cy="11" r="6" fill="none" stroke="currentColor" stroke-width="0.6" stroke-dasharray="2 1.5"/>' +
             '</svg>');
        want.push({ key: 'seg' + i, kind: 'seg', dir: dir, flip: dir < 0, x: tp[0], y: tp[1], z: tp[2],
          html: '<div class="tree-annual-ring">' + ringSvg + '<span class="tree-ring-numeral">' + roman + '</span></div>' +
                '<b>' + sg.name + '</b><s>主线 · ' + sg.events + ' 事件</s>' });
      }
    }
    if (near) {
      want.push({ key: 'near', kind: 'near', dir: 1, flip: false, x: near.x, y: near.y, z: near.z,
        html: '<b>' + near.name + '</b><s>剧情线 · ' + near.ev + ' 事件</s>' });
    }
    for (i = 0; i < want.length; i++) {
      var w = want[i], s = slots[i];
      if (!s) {
        s = { node: document.createElement('div'), html: '', kind: '', key: '', flip: false };
        s.node.className = 'm';
        el.appendChild(s.node);
        slots.push(s);
      }
      if (s.html !== w.html || s.kind !== w.kind || s.flip !== w.flip) {
        s.node.className = 'm k-' + w.kind + (w.flip ? ' flip' : '');
        s.node.innerHTML = w.html;
        s.html = w.html; s.kind = w.kind; s.flip = w.flip;
      }
      s.key = w.key; s.x = w.x; s.y = w.y; s.z = w.z; s.dir = w.dir; s.want = true;
    }
    for (i = want.length; i < slots.length; i++) slots[i].want = false;
    st.marks = want.length;
    st.labels = want.length;
  }

  function placeOne(s, A, S) {
    if (!s.want) { s.node.classList.remove('on'); return; }
    var q = (S && S.bend) ? tryFn(function () { return S.bend([s.x, s.y, s.z]); }) : null;
    if (!q) q = [s.x, s.y, s.z];
    var sc = tryFn(function () { return A.toScreen(q); });
    if (!sc || !sc.on) { s.node.classList.remove('on'); return; }
    var K = window.CLLabelKernel;
    var ox = (K && K.leadOffset) ? K.leadOffset : 14;
    if (s.kind === 'seg' && s.dir < 0) ox = -(ox + w);
    var x = sc.x + ox, y = sc.y - 12;
    var nudgeList = (K && K.nudge) ? K.nudge : NUDGE;
    for (var k = 0; k < nudgeList.length; k++) {
      if (!overlaps(x, y + nudgeList[k], w, hh)) { y += nudgeList[k]; break; }
    }
    var vw = window.innerWidth || 1400, vh = window.innerHeight || 900;
    if (K && typeof K.clampViewport === 'function') {
      var clamped = K.clampViewport(x, y, w, hh, vw, vh, (s.kind === 'seg' && s.dir < 0) ? -1 : 1);
      x = clamped.x; y = clamped.y;
    } else {
      var LM = 8;
      var leadL = (s.kind === 'seg' && s.dir < 0) ? 0 : 14;
      var leadR = (s.kind === 'seg' && s.dir < 0) ? 14 : 0;
      x = Math.max(LM + leadL, Math.min(x, vw - w - LM - leadR));
      y = Math.max(LM, Math.min(y, vh - hh - LM));
    }
    s.node.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
    s.node.classList.add('on');
    s.px = Math.round(x); s.py = Math.round(y);
  }

  function place() {
    if (!el || !vis) return;
    var A = window.CLTreeAnchor;
    if (!A || !A.toScreen) return;
    var S = window.CLTreeSway;
    for (var i = 0; i < slots.length; i++) placeOne(slots[i], A, S);
    st.x = slots.length ? slots[0].px : null;
    st.y = slots.length ? slots[0].py : null;
  }

  function treeShown() {
    var S = window.CLTreeStage;
    if (!S || !S.stats) return false;
    var ss = tryFn(S.stats);
    return !!(ss && ss.active);
  }

  function shapeNow() {
    var g = window.CLTreeGhost;
    return (g && g.shapeOf) ? tryFn(g.shapeOf) : null;
  }

  var lastMx = null, lastMy = null;
  function update(s) {
    frame++;
    if (!mounted && !build()) return;
    if (s && s.muted !== undefined) setOn(!s.muted);
    var shape = shapeNow();
    /* v43 性能：指针没动就不重算最近枝（nearestBranch 要把几千个枝点全部投影一遍）；
     * 树在呼吸摇曳，所以每 12 帧仍强制复算一次，保证高亮跟着枝走。 */
    var moved = (mx !== lastMx || my !== lastMy);
    var hov = (mx !== null && my !== null && shape && frame % 2 === 0 && (moved || frame % 12 === 0));
    if (hov) { lastMx = mx; lastMy = my; }
    if (hov) {
      var nb = nearestBranch(mx, my, shape);
      if (nb) {
        var obj = nb.obj, tip = tipOf(obj);
        var nm = nameOf[String(obj.threadId)] || (obj.threadId ? String(obj.threadId) : '枝');
        near = { name: nm, ev: eventsOn(obj, shape), x: tip[0], y: tip[1], z: tip[2] };
        st.near = nm; st.nearEv = near.ev;
      }
    }
    if (frame % REFRESH === 1) {
      rebuildNames();
      renderContent(shapeNow());
    }
    if (hov && !nb && near) {
      near = null; st.near = null; st.nearEv = 0;
      renderContent(shapeNow());
    }
    var wantV = shown && !muted && treeShown();
    var wasVis = vis;
    vis = !!wantV;
    st.visible = vis;
    if (!el) return vis;
    if (!vis) {
      for (var i = 0; i < slots.length; i++) slots[i].node.classList.remove('on');
      return vis;
    }
    if (vis && !wasVis) {
      if (!slots.length) { rebuildNames(); renderContent(shapeNow()); }
      place();
    } else if (frame % EVERY === 0) {
      place();
    }
    return vis;
  }

  function setOn(v) { muted = !v; return vis; }
  function show(v) { shown = (v == null) ? true : !!v; return vis; }
  function visible() { return !!vis; }

  function hover(x, y) {
    mx = (typeof x === 'number' && isFinite(x)) ? x : null;
    my = (typeof y === 'number' && isFinite(y)) ? y : null;
    return near;
  }
  function unhover() { mx = null; my = null; if (near) { near = null; st.near = null; st.nearEv = 0; } }
  function bindPointer() {
    if (!document.addEventListener) return;
    document.addEventListener('pointermove', function (e) { mx = e.clientX; my = e.clientY; }, { passive: true });
    document.addEventListener('pointerleave', unhover, { passive: true });
    window.addEventListener('blur', unhover, false);
  }

  function stats() {
    return { mounted: mounted, visible: !!vis, muted: muted, shown: shown,
      frame: frame, marks: st.marks, labels: st.labels, near: st.near, nearEv: st.nearEv,
      ringErr: st.ringErr, x: st.x, y: st.y, slots: slots.length,
      texts: slots.map(function (s) { return { key: s.key, kind: s.kind, on: !!s.want, html: s.html }; }) };
  }

  var API = {
    name: 'tree-marks',
    build: function () { build(); return stats(); },
    update: update,
    dispose: function () {
      if (el && el.parentNode) el.parentNode.removeChild(el);
      el = null; mounted = false; near = null; slots = [];
    },
    setOn: setOn,
    show: show,
    visible: visible,
    hover: hover,
    unhover: unhover,
    stats: stats
  };
  window.CLTreeMarks = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  function boot() { build(); bindPointer(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); hook(); }, false);
  } else { boot(); hook(); }
})();
