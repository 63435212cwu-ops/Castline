(function (g) {
  'use strict';

  var VERSION = '47';
  var MAIN_MAX = 5;
  var BRANCH_POOL = 4;
  var CAP_DEFAULT = 8;
  var KERNEL = g.CLLabelKernel || null;
  var NUDGE_TRIES = (KERNEL && KERNEL.nudgeTries) || 8;
  var EST_CH = 11.6;
  var EST_H = 15;

  function fin(v) { return typeof v === 'number' && isFinite(v); }
  function r2(v) { return Math.round(v * 100) / 100; }
  function txt(v) { return (v == null) ? '' : String(v); }
  function now() {
    try { return (g.performance && g.performance.now) ? g.performance.now() : 0; } catch (e) { return 0; }
  }

  function rectOf(el) {
    if (!el) return null;
    var r;
    try { r = el.getBoundingClientRect(); } catch (e) { return null; }
    if (!r || (r.width <= 0 && r.height <= 0)) return null;
    return r;
  }
  function obstacleRects() {
    var out = [], d = g.document, r;
    try { r = rectOf(d.getElementById('brand')); if (r) out.push(r); } catch (e) { void e; }
    try { r = rectOf(d.getElementById('index')); if (r) out.push(r); } catch (e2) { void e2; }
    try { r = rectOf(d.querySelector('.cl-o3-deck')); if (r) out.push(r); } catch (e3) { void e3; }
    try { r = rectOf(d.querySelector('.cl-o3-ruler')); if (r) out.push(r); } catch (e4) { void e4; }
    try { r = rectOf(d.querySelector('#dock.on .panel')); if (r) out.push(r); } catch (e5) { void e5; }
    try { r = rectOf(d.getElementById('shellMenuBtn')); if (r) out.push(r); } catch (e6) { void e6; }
    try { r = rectOf(d.getElementById('shellIndexBtn')); if (r) out.push(r); } catch (e7) { void e7; }
    return out;
  }
  function dockOnFlag() {
    try {
      var dk = g.document.getElementById('dock');
      return !!(dk && dk.className && dk.className.indexOf('on') >= 0);
    } catch (e) { return false; }
  }
  function compactFlag() {
    try { return !!g.document.getElementById('shellMenuBtn'); } catch (e) { return false; }
  }

  function create(view, pick, tokens) {
    function grabPick() {
      var v = view, x = null, i, k = ['picker', 'pick'];
      if (!v) return null;
      for (i = 0; i < k.length; i++) {
        x = v[k[i]];
        if (typeof x === 'function' && k[i] === 'picker') { try { x = x.call(v); } catch (e) { x = null; } }
        else if (typeof x === 'function') { try { x = x.call(v); } catch (e2) { x = null; } }
        if (x && typeof x.screenOfLine === 'function') return x;
      }
      return null;
    }
    if (!pick || typeof pick.screenOfLine !== 'function') pick = grabPick() || pick || null;
    var tok = tokens || g.CLOrbit3DTokens || null;
    var CAP = CAP_DEFAULT;
    if (tok && tok.BUDGET && fin(tok.BUDGET.LABELS)) CAP = tok.BUDGET.LABELS | 0;
    if (CAP < 1) CAP = 1;

    var owned = false, root = null;
    if (view && typeof view.layer === 'function') {
      var cand = null;
      try { cand = view.layer('labels'); } catch (e) { cand = null; }
      if (cand && cand.nodeType === 1 && cand.className &&
        String(cand.className).indexOf('cl-o3-labels') >= 0) root = cand;
    }
    if (!root) {
      root = document.createElement('div');
      root.className = 'cl-o3-labels';
      owned = true;
      (document.body || document.documentElement).appendChild(root);
    }
    root.setAttribute('aria-hidden', 'true');
    root.style.pointerEvents = 'none';

    var mains = [];
    var brs = [];
    var genesisRec = null;
    var epochRecs = [];
    var genesisData = null;
    var epochsData = [];
    var model = { main: [], branch: {} };
    var geomRef = null, shown = true, dead = false;
    var lastSig = -2, lastKey = '', updates = 0, writes = 0, lastMs = 0, moving = 0, measures = 0, pinCount = 0;
    var boxes = [];

    function mkGenesisBadge() {
      var el = document.createElement('div');
      el.className = 'cl-o3-lab cl-o3-genesis-badge';
      el.setAttribute('data-kind', 'genesis');
      el.setAttribute('data-valid', '1');
      el.style.transitionProperty = 'opacity, color, transform';
      el.style.padding = '2px 8px';
      el.style.borderRadius = '999px';
      el.style.background = 'rgba(24, 18, 12, 0.78)';
      el.style.border = '1px solid rgba(224, 169, 109, 0.55)';
      el.style.color = 'var(--warm)';
      el.style.boxShadow = '0 0 10px rgba(224, 169, 109, 0.35)';
      el.style.fontSize = '.70rem';
      el.style.fontWeight = '600';
      el.style.letterSpacing = '.06em';
      el.appendChild(document.createTextNode(''));
      el.style.display = 'none';
      root.appendChild(el);
      return { el: el, name: '', w: 0, h: 0, need: true, tx: '', cls: '', live: false };
    }
    function mkEpochBadge() {
      var el = document.createElement('div');
      el.className = 'cl-o3-lab cl-o3-epoch-badge';
      el.setAttribute('data-kind', 'epoch');
      el.setAttribute('data-valid', '1');
      el.style.transitionProperty = 'opacity, color, transform';
      el.style.padding = '1px 6px';
      el.style.borderRadius = '3px';
      el.style.background = 'rgba(16, 20, 28, 0.72)';
      el.style.border = '1px solid rgba(130, 160, 210, 0.35)';
      el.style.color = 'var(--ink-2)';
      el.style.fontSize = '.64rem';
      el.style.letterSpacing = '.04em';
      el.appendChild(document.createTextNode(''));
      el.style.display = 'none';
      root.appendChild(el);
      return { el: el, name: '', w: 0, h: 0, need: true, tx: '', cls: '', live: false };
    }
    function mkLabel(kind) {
      var el = document.createElement('div');
      el.className = 'cl-o3-lab';
      el.setAttribute('data-kind', kind);
      el.setAttribute('data-valid', '1');
      el.style.transitionProperty = 'opacity, color';
      el.appendChild(document.createTextNode(''));
      var rec = { el: el, name: null, sub: null, valid: null, key: null, w: 0, h: 0,
        need: true, tx: '', cls: '', sub2: null, mark: null, live: false };
      if (kind === 'main') {
        rec.sub2 = document.createElement('span');
        rec.sub2.className = 'cl-o3-lead';
        el.appendChild(rec.sub2);
      } else {
        rec.mark = document.createElement('i');
        rec.mark.appendChild(document.createTextNode('待校对'));
      }
      el.style.display = 'none';
      root.appendChild(el);
      return rec;
    }
    function pool(arr, kind, n) {
      while (arr.length < n) arr.push(mkLabel(kind));
      return arr;
    }

    function setText(rec, name, sub, valid) {
      if (rec.name !== name) { rec.el.firstChild.nodeValue = name; rec.name = name; rec.need = true; }
      if (rec.sub2 && rec.sub !== sub) {
        rec.sub2.firstChild ? (rec.sub2.firstChild.nodeValue = sub)
          : rec.sub2.appendChild(document.createTextNode(sub));
        rec.sub2.style.display = sub ? '' : 'none';
        rec.sub = sub; rec.need = true;
      }
      var v = valid ? '1' : '0';
      if (rec.valid !== v) {
        rec.el.setAttribute('data-valid', v);
        if (rec.mark) {
          if (!valid) { if (rec.mark.parentNode !== rec.el) rec.el.appendChild(rec.mark); }
          else if (rec.mark.parentNode === rec.el) rec.el.removeChild(rec.mark);
        }
        rec.valid = v; rec.need = true;
      }
    }

    function measure(rec) {
      if (!rec.need) return;
      var w = 0, h = 0;
      if (shown) { w = rec.el.offsetWidth; h = rec.el.offsetHeight; measures++; }
      if (w > 0 && h > 0) { rec.w = w + 2; rec.h = h + 2; rec.need = false; }
      else {
        rec.w = 10 + txt(rec.name).length * EST_CH;
        rec.h = EST_H * (rec.sub ? 2 : 1) + 4;
      }
    }

    function cls(rec, want) {
      if (rec.cls === want) return;
      var el = rec.el;
      if (want === 'on') { el.classList.add('is-on'); el.classList.remove('is-hover'); }
      else if (want === 'hover') { el.classList.add('is-hover'); el.classList.remove('is-on'); }
      else { el.classList.remove('is-on'); el.classList.remove('is-hover'); }
      rec.cls = want;
    }

    function place(rec, x, y) {
      var s = 'translate3d(' + r2(x) + 'px,' + r2(y) + 'px,0) translate(-50%,-100%)';
      if (rec.tx !== s) { rec.el.style.transform = s; rec.tx = s; writes++; }
      if (!rec.live) { rec.el.style.display = ''; rec.live = true; }
    }
    function park(rec) {
      if (rec.live) { rec.el.style.display = 'none'; rec.live = false; }
      cls(rec, '');
    }

    function pinRec(rec, fullText) {
      var el = rec.el;
      if (el.__pinned) return;
      el.__pinned = true;
      el.setAttribute('title', fullText || '');
      el.style.width = '4px'; el.style.height = '4px'; el.style.minWidth = '0';
      el.style.padding = '0'; el.style.overflow = 'hidden'; el.style.borderRadius = '50%';
      if (rec.sub2) rec.sub2.style.display = 'none';
      if (rec.mark && rec.mark.parentNode === el) el.removeChild(rec.mark);
      pinCount++;
    }
    function unpinStyle(el) {
      if (!el.__pinned) return false;
      el.__pinned = false;
      el.removeAttribute('title');
      el.style.width = ''; el.style.height = ''; el.style.minWidth = '';
      el.style.padding = ''; el.style.overflow = ''; el.style.borderRadius = '';
      return true;
    }
    function unpinRec(rec) {
      if (unpinStyle(rec.el)) { rec.need = true; rec.name = null; rec.sub = null; rec.valid = null; }
    }

    function clampAnchor(x, y, hw, hh, W, H) {
      var nx = x, ny = y;
      if (x - hw < 4) nx = hw + 4; else if (x + hw > W - 4) nx = W - 4 - hw;
      if (y - hh < 8) ny = hh + 8; else if (y > H - 4) ny = H - 4;
      return { x: nx, y: ny };
    }

    function threadOf(id) {
      if (!view || typeof view.threadAt !== 'function' || id == null) return null;
      try { return view.threadAt(id); } catch (e) { return null; }
    }

    function rebuild(desc) {
      geomRef = desc || null;
      model = { main: [], branch: {} };
      var arcs = (desc && desc.arcs) || [], i, j;
      for (i = 0; i < arcs.length; i++) {
        var a = arcs[i];
        if (!a || a.lineId == null) continue;
        var th = threadOf(a.lineId);
        var title = txt((th && th.title) || a.title);
        var ok = (a.valid !== false) && !a.anchored;
        if (th && (th.anchored === true || (th.topologyStatus && th.topologyStatus !== 'confirmed'))) ok = false;
        if (a.kind === 'main') {
          var segs = (a.segments && a.segments.length) ? a.segments : null;
          if (segs) {
            for (j = 0; j < segs.length; j++) {
              if (model.main.length >= MAIN_MAX) break;
              var lead = txt((segs[j] && segs[j].lead) || a.lead || (th && th.lead));
              model.main.push({ key: a.lineId + '#' + j, name: lead || title || txt(a.lineId),
                sub: (title && title !== lead) ? title : '', valid: ok });
            }
          } else if (model.main.length < MAIN_MAX) {
            var l2 = txt(a.lead || (th && th.lead));
            model.main.push({ key: a.lineId, name: l2 || title || txt(a.lineId),
              sub: (title && title !== l2) ? title : '', valid: ok });
          }
        } else {
          model.branch[a.lineId] = { key: a.lineId,
            name: title || txt(a.lead || (th && th.lead)) || txt(a.lineId), valid: ok };
        }
      }
      pool(mains, 'main', Math.min(MAIN_MAX, model.main.length));
      if (desc && desc.genesis && fin(desc.genesis.evIdx)) {
        genesisData = desc.genesis;
        if (!genesisRec) genesisRec = mkGenesisBadge();
        genesisRec.need = true;
      } else {
        genesisData = null;
      }
      if (desc && desc.epochs && desc.epochs.length) {
        epochsData = desc.epochs.slice(0, 5);
        while (epochRecs.length < epochsData.length) epochRecs.push(mkEpochBadge());
        for (j = 0; j < epochRecs.length; j++) epochRecs[j].need = true;
      } else {
        epochsData = [];
      }
      lastSig = -2; lastKey = '';
    }

    function branchOfEvent(ev) {
      if (!fin(ev) || ev < 0 || !pick || typeof pick.linesOf !== 'function') return null;
      var ls;
      try { ls = pick.linesOf(ev); } catch (e) { return null; }
      if (!ls) return null;
      for (var i = 0; i < ls.length; i++) { if (model.branch[ls[i]]) return ls[i]; }
      return null;
    }

    function readState() {
      var st = null;
      if (view && typeof view.state === 'function') { try { st = view.state(); } catch (e) { st = null; } }
      st = st || {};
      var plot = (st.mode === 'plot') || (st.visible === true && st.mode == null);
      var sel = (st.thread != null && st.thread !== '') ? st.thread : null;
      var hov = (st.hoverThread != null && st.hoverThread !== '') ? st.hoverThread : null;
      if (!hov) hov = branchOfEvent(fin(st.hoverEv) ? st.hoverEv : st.hover);
      if (!sel) sel = branchOfEvent(fin(st.focusEv) ? st.focusEv : st.focus);
      if (sel != null && !model.branch[sel]) sel = null;
      if (hov != null && !model.branch[hov]) hov = null;
      if (hov != null && hov === sel) hov = null;
      return { plot: plot, sel: sel, hov: hov };
    }

    function overlaps(n, x0, y0, x1, y1) {
      for (var i = 0; i < n; i += 4) {
        if (x0 < boxes[i + 2] && x1 > boxes[i] && y0 < boxes[i + 3] && y1 > boxes[i + 1]) return true;
      }
      return false;
    }

    function update() {
      if (dead) return;
      var t0 = now(), i;
      if (!pick || typeof pick.screenOfLine !== 'function') pick = grabPick() || pick;
      var desc = (pick && typeof pick.geom === 'function') ? pick.geom() : null;
      if (!desc && view && typeof view.desc === 'function') { try { desc = view.desc(); } catch (e) {} }
      if (desc !== geomRef) rebuild(desc);

      var st = readState();
      var sig = (pick && typeof pick.sig === 'function') ? pick.sig() : -1;
      var key = (st.plot ? '1' : '0') + '|' + shown + '|' + txt(st.sel) + '|' + txt(st.hov) +
        '|' + (dockOnFlag() ? 1 : 0) + (compactFlag() ? 1 : 0) +
        '|' + (g.innerWidth || 0) + 'x' + (g.innerHeight || 0);
      if (sig === lastSig && key === lastKey) { updates++; lastMs = now() - t0; return; }
      lastSig = sig; lastKey = key;
      updates++;

      if (!st.plot || !shown || sig < 0) {
        for (i = 0; i < mains.length; i++) park(mains[i]);
        for (i = 0; i < brs.length; i++) park(brs[i]);
        if (genesisRec) park(genesisRec);
        for (i = 0; i < epochRecs.length; i++) park(epochRecs[i]);
        moving = 0; lastMs = now() - t0;
        return;
      }

      var want = [], n = Math.min(model.main.length, mains.length, MAIN_MAX);
      for (i = 0; i < n && want.length < CAP; i++) want.push({ rec: mains[i], m: model.main[i], cls: '' });

      var act = [];
      if (st.sel != null) act.push({ id: st.sel, cls: 'on' });
      if (st.hov != null) act.push({ id: st.hov, cls: 'hover' });
      pool(brs, 'branch', Math.min(BRANCH_POOL, Math.max(1, act.length)));
      var used = 0;
      for (i = 0; i < act.length && want.length < CAP && used < brs.length; i++) {
        want.push({ rec: brs[used], m: model.branch[act[i].id], cls: act[i].cls });
        used++;
      }
      for (i = used; i < brs.length; i++) park(brs[i]);
      for (i = n; i < mains.length; i++) park(mains[i]);

      for (i = 0; i < want.length; i++) {
        var w = want[i];
        unpinRec(w.rec);
        setText(w.rec, w.m.name, w.rec.sub2 ? txt(w.m.sub) : '', w.m.valid !== false);
        measure(w.rec);
      }

      var c = (pick && typeof pick.center === 'function') ? pick.center() : null;
      var cx = (c && fin(c[0])) ? c[0] : 0, cy = (c && fin(c[1])) ? c[1] : 0;
      var W = g.innerWidth || 0, H = g.innerHeight || 0;
      var obs = obstacleRects(), nb = 0, oi;
      for (oi = 0; oi < obs.length; oi++) {
        var ob = obs[oi];
        boxes[nb] = ob.left; boxes[nb + 1] = ob.top; boxes[nb + 2] = ob.right; boxes[nb + 3] = ob.bottom;
        nb += 4;
      }
      var pending = 0;
      moving = 0;
      for (i = 0; i < want.length; i++) {
        var rec = want[i].rec, m = want[i].m;
        if (rec.need) pending = 1;
        var p = null;
        if (pick && typeof pick.screenOfLine === 'function') p = pick.screenOfLine(m.key);
        if (!p || !fin(p[0]) || !fin(p[1])) { park(rec); continue; }
        var x = p[0], y = p[1], hw = rec.w * 0.5, hh = rec.h;
        var dx = x - cx, dy = y - cy, dl = Math.sqrt(dx * dx + dy * dy);
        if (dl > 1e-3) { dx /= dl; dy /= dl; } else { dx = 0; dy = -1; }
        var k = 0;
        while (k < NUDGE_TRIES && overlaps(nb, x - hw, y - hh, x + hw, y)) {
          x += dx * rec.h; y += dy * rec.h; k++;
        }
        var an = clampAnchor(x, y, hw, hh, W, H);
        x = an.x; y = an.y;
        if (overlaps(nb, x - hw, y - hh, x + hw, y)) {
          pinRec(rec, m.name);
          var pp = clampAnchor(p[0], p[1], 2, 2, W, H);
          boxes[nb] = pp.x - 2; boxes[nb + 1] = pp.y - 2; boxes[nb + 2] = pp.x + 2; boxes[nb + 3] = pp.y + 2;
          nb += 4;
          place(rec, pp.x, pp.y);
          cls(rec, want[i].cls);
          moving++;
          continue;
        }
        unpinRec(rec);
        boxes[nb] = x - hw; boxes[nb + 1] = y - hh; boxes[nb + 2] = x + hw; boxes[nb + 3] = y;
        nb += 4;
        place(rec, x, y);
        cls(rec, want[i].cls);
        moving++;
      }

      if (genesisData && genesisRec) {
        var gTitle = '⬡ ' + (genesisData.label || '纪元起点 · 启航发端');
        if (genesisRec.name !== gTitle) {
          genesisRec.el.firstChild.nodeValue = gTitle;
          genesisRec.name = gTitle;
          genesisRec.need = true;
        }
        if (genesisRec.need) {
          unpinStyle(genesisRec.el);
          if (shown && genesisRec.el.offsetWidth) {
            genesisRec.w = genesisRec.el.offsetWidth + 4;
            genesisRec.h = genesisRec.el.offsetHeight + 2;
            genesisRec.need = false;
          } else {
            genesisRec.w = 120;
            genesisRec.h = 22;
          }
        }
        var gp = null;
        if (pick && typeof pick.screenOf === 'function') {
          gp = pick.screenOf(genesisData.evIdx, 'genesis') || pick.screenOf(genesisData.evIdx);
        }
        if (gp && fin(gp[0]) && fin(gp[1])) {
          var gx = gp[0], gy = gp[1] - 22, ghw = genesisRec.w * 0.5, ghh = genesisRec.h;
          var ga = clampAnchor(gx, gy, ghw, ghh, W, H);
          gx = ga.x; gy = ga.y;
          if (overlaps(nb, gx - ghw, gy - ghh, gx + ghw, gy)) {
            pinRec(genesisRec, gTitle);
            var gpp = clampAnchor(gp[0], gp[1] - 22, 2, 2, W, H);
            boxes[nb] = gpp.x - 2; boxes[nb + 1] = gpp.y - 2; boxes[nb + 2] = gpp.x + 2; boxes[nb + 3] = gpp.y + 2;
            nb += 4;
            place(genesisRec, gpp.x, gpp.y);
          } else {
            unpinStyle(genesisRec.el);
            boxes[nb] = gx - ghw; boxes[nb + 1] = gy - ghh; boxes[nb + 2] = gx + ghw; boxes[nb + 3] = gy;
            nb += 4;
            place(genesisRec, gx, gy);
          }
          genesisRec.el.style.opacity = '1';
          moving++;
        } else {
          park(genesisRec);
        }
      } else if (genesisRec) {
        park(genesisRec);
      }

      for (i = 0; i < epochsData.length; i++) {
        var epItem = epochsData[i], epRec = epochRecs[i];
        if (!epItem || !epRec) continue;
        var epTitle = epItem.title || ('纪元阶段 · 第 ' + epItem.epochIdx + ' 幕');
        if (epRec.name !== epTitle) {
          epRec.el.firstChild.nodeValue = epTitle;
          epRec.name = epTitle;
          epRec.need = true;
        }
        if (epRec.need) {
          if (shown && epRec.el.offsetWidth) {
            epRec.w = epRec.el.offsetWidth + 2;
            epRec.h = epRec.el.offsetHeight + 2;
            epRec.need = false;
          } else {
            epRec.w = 88;
            epRec.h = 18;
          }
        }
        var epp = null;
        if (pick && typeof pick.screenOf === 'function') {
          epp = pick.screenOf(epItem.evIdx);
        }
        if (epp && fin(epp[0]) && fin(epp[1])) {
          var ex = epp[0], ey = epp[1] - 14, ehw = epRec.w * 0.5, ehh = epRec.h;
          var ea = clampAnchor(ex, ey, ehw, ehh, W, H);
          ex = ea.x; ey = ea.y;
          if (overlaps(nb, ex - ehw, ey - ehh, ex + ehw, ey)) {
            pinRec(epRec, epTitle);
            var epp2 = clampAnchor(epp[0], epp[1] - 14, 2, 2, W, H);
            boxes[nb] = epp2.x - 2; boxes[nb + 1] = epp2.y - 2; boxes[nb + 2] = epp2.x + 2; boxes[nb + 3] = epp2.y + 2;
            nb += 4;
            place(epRec, epp2.x, epp2.y);
          } else {
            unpinStyle(epRec.el);
            boxes[nb] = ex - ehw; boxes[nb + 1] = ey - ehh; boxes[nb + 2] = ex + ehw; boxes[nb + 3] = ey;
            nb += 4;
            place(epRec, ex, ey);
          }
          epRec.el.style.opacity = '0.82';
          moving++;
        } else {
          park(epRec);
        }
      }
      for (i = epochsData.length; i < epochRecs.length; i++) park(epochRecs[i]);

      if (pending) lastSig = -2;
      lastMs = now() - t0;
    }

    function setVisible(on) {
      on = !!on;
      if (on === shown) return shown;
      shown = on;
      root.style.display = on ? '' : 'none';
      lastKey = '';
      if (on) {
        for (var i = 0; i < mains.length; i++) mains[i].need = true;
        for (i = 0; i < brs.length; i++) brs[i].need = true;
        if (genesisRec) genesisRec.need = true;
        for (i = 0; i < epochRecs.length; i++) epochRecs[i].need = true;
      }
      return shown;
    }

    function destroy() {
      if (dead) return;
      dead = true;
      if (owned) { if (root.parentNode) root.parentNode.removeChild(root); }
      else {
        for (var i = 0; i < mains.length; i++) { if (mains[i].el.parentNode === root) root.removeChild(mains[i].el); }
        for (i = 0; i < brs.length; i++) { if (brs[i].el.parentNode === root) root.removeChild(brs[i].el); }
        if (genesisRec && genesisRec.el.parentNode === root) root.removeChild(genesisRec.el);
        for (i = 0; i < epochRecs.length; i++) {
          if (epochRecs[i].el.parentNode === root) root.removeChild(epochRecs[i].el);
        }
      }
      mains = []; brs = []; genesisRec = null; epochRecs = [];
      model = { main: [], branch: {} }; geomRef = null; boxes = [];
    }

    function countOwn() {
      var n = 0, i;
      for (i = 0; i < mains.length; i++) n += 1 + mains[i].el.getElementsByTagName('*').length;
      for (i = 0; i < brs.length; i++) n += 1 + brs[i].el.getElementsByTagName('*').length;
      if (genesisRec) n += 1 + genesisRec.el.getElementsByTagName('*').length;
      for (i = 0; i < epochRecs.length; i++) n += 1 + epochRecs[i].el.getElementsByTagName('*').length;
      return n;
    }
    function stats() {
      var nodes = dead ? 0 : (owned ? 1 + root.getElementsByTagName('*').length
        : countOwn());
      var bn = 0, kk; for (kk in model.branch) { if (Object.prototype.hasOwnProperty.call(model.branch, kk)) bn++; }
      return { version: VERSION, nodes: nodes,
        pool: mains.length + brs.length + (genesisRec ? 1 : 0) + epochRecs.length,
        main: model.main.length, branch: bn, moving: moving, cap: CAP,
        hasGenesis: !!(genesisData && genesisRec), epochs: epochsData.length,
        visible: shown && !dead, updates: updates, writes: writes, measures: measures,
        lastMs: Math.round(lastMs * 1000) / 1000, sig: lastSig, pinCount: pinCount };
    }

    return { version: VERSION, update: update, setVisible: setVisible,
      destroy: destroy, stats: stats, layer: function () { return root; } };
  }

  g.CLOrbit3DLabels = { name: 'CLOrbit3DLabels', version: VERSION, create: create };
})(typeof window !== 'undefined' ? window : this);
