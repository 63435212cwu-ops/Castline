/*!
 * @role component
 * @owns js/sky/sky-compass-fan.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/3
 *
 * 罗盘关键事件扇出（Q9.4）：悬停 / 键盘聚焦一颗因果珠（含密度带上就近取到的回）→ 该回全部事件短名沿发丝引线扇形展开。
 * 左右两摞、行距 FAN.pitch，锚点落在以珠为心的圆弧上（下排外张、上排内收），引线自珠边径向拉出；按回内次序顺时针读（左外下→内上→顶→右内上→外下）。
 * 贪心避让：槽不压标题与两侧细线、带子与珠、链身、首尾回数、关系对象、轴签、HUD，不出屏；放不下的收成「+N」。离开收回；悬停卡片让到扇面旁。
 * 键盘：珠可 Tab；←/→ 逐回（带上无珠的回由带子持焦 + 游标）、↑/↓ 相邻的珠、Home/End；Enter/空格展开、Esc 收回（再按交还壳层退出罗盘）。
 * 方向键在窗口捕获阶段截下（本脚本先于 sky-shell 加载），不漏给图上的旋转。只读 sky-compass 的排版结果；减弱动效直接落终态。
 */
(function (g) {
  'use strict';
  var doc = g.document;
  var hk = null, svg = null, grp = null, cur = -1, at0 = 0, keyK = -1, box = null, last = null;

  function F() { return g.CLSkyTokens.FAN; }
  var now = g.CLSkyUtil.now, mk = g.CLSkyUtil.svg;
  function f1(v) { return v.toFixed(1); }
  function at(el, o) { for (var k in o) el.setAttribute(k, typeof o[k] === 'number' ? f1(o[k]) : o[k]); return el; }
  function hit(a, b, pad) { return a[0] < b[2] + pad && a[2] > b[0] - pad && a[1] < b[3] + pad && a[3] > b[1] - pad; }
  function hitAny(a, list, pad) { for (var i = 0; i < list.length; i++) if (hit(a, list[i], pad)) return true; return false; }
  function short(t, n) { t = String(t || ''); return t.length > n ? t.slice(0, n) + '…' : t; }
  function clear() { while (grp.firstChild) grp.removeChild(grp.firstChild); }

  /* 扇面槽：每侧 m 行，最低一行离珠 rise；锚点在半径 R 的圆弧上（下排外张、上排内收）+ 顶上一个居中槽 */
  function slots(C, m, rise, P) {
    var R = rise + (m - 1) * P + 10, out = [], j, s;
    for (s = -1; s <= 1; s += 2) for (j = 0; j < m; j++) {
      var dy = rise + j * P;
      out.push({ side: s, j: j, ax: C[0] + s * Math.max(12, Math.sqrt(Math.max(0, R * R - dy * dy))), ay: C[1] - dy });
    }
    out.push({ side: 0, j: m, ax: C[0], ay: C[1] - rise - m * P });
    return out;
  }
  function boxOf(sl, w) {
    if (!sl.side) return [sl.ax - w / 2 - 1, sl.ay - 13, sl.ax + w / 2 + 1, sl.ay - 1];
    return sl.side > 0 ? [sl.ax + 3, sl.ay - 7, sl.ax + 5 + w, sl.ay + 6] : [sl.ax - 5 - w, sl.ay - 7, sl.ax - 3, sl.ay + 6];
  }
  /* 从空槽里挑 n 个：两侧均分（奇数条且顶槽空着就放顶上），一侧不够让给另一侧；再按顺时针排好 */
  function choose(free, n) {
    var L = free.filter(function (s) { return s.side < 0; }), R = free.filter(function (s) { return s.side > 0; }), T = free.filter(function (s) { return !s.side; });
    var top = n % 2 === 1 && T.length ? 1 : 0, k = n - top, kL = Math.min(L.length, Math.ceil(k / 2)), kR = Math.min(R.length, k - kL);
    kL = Math.min(L.length, k - kR);
    if (kL + kR + top < n && T.length && !top) top = 1;
    var out = L.slice(0, kL).concat(top ? T : [], R.slice(0, kR).reverse());
    if (!kR && !top) out.reverse();   /* 只剩左摞（珠贴右屏边）：自上而下读 */
    return out.slice(0, n);
  }
  /* 轴签此刻的框：「扫过范围」刚开罗盘时还没学全，建扇时现读一次 */
  function liveLabs() {
    var out = [];
    Array.prototype.forEach.call(doc.querySelectorAll('#labels .cl-lab.attr.on, #labels .cl-lab.meta.on'), function (el) {
      var r = el.getBoundingClientRect();
      if (r.width > 0 && g.getComputedStyle(el).visibility !== 'hidden') out.push([r.left, r.top - 2, r.right, r.bottom + 2]);
    });
    return out;
  }
  function layout(st, d, w) {
    var P = F(), av = st.avoid || {}, W = av.W || g.innerWidth, top = (av.top || 60) + 4, bot = av.bottom || g.innerHeight - 30, cg = st.chainGeo;
    var rb = st.band ? Math.max(d.r, st.band.hMax + 1) : Math.max(d.r, 2), C = [d.x, d.y], rise = Math.max(P.rise, rb + 10), n = w.length, wm = Math.max.apply(null, w);
    var obs = [].concat(av.fixed || [], av.sats || [], av.labs || [], av.hud || [], (av.beads || []).filter(function (b) { return b[4] !== d; }), liveLabs());
    if (cg && cg.chord > 0 && !st.band) for (var x = cg.x0; x <= cg.x1; x += 12) {   /* 链身（细线）也算障碍 */
      var u = (x - cg.cx) / (cg.chord / 2), y = cg.y0 + cg.sag * (1 - u * u); obs.push([x - 6, y - 2, x + 6, y + 2]);
    }
    var best = [];
    for (var m = Math.max(1, Math.ceil(n / 2)); m <= P.rows; m++) {
      var free = slots(C, m, rise, P.pitch).filter(function (sl) { var b = boxOf(sl, wm); return b[0] >= 6 && b[2] <= W - 6 && b[1] >= top && b[3] <= bot && !hitAny(b, obs, P.pad); });
      var c = choose(free, n);
      if (c.length > best.length) best = c;
      if (best.length >= n) break;
    }
    if (!best.length) best = [slots(C, 1, rise, P.pitch).pop()];   /* 一个空槽都没有：珠正上方至少留「+N」 */
    return { C: C, rb: rb, slots: best };
  }

  /* how：0 展开 · 1 快速换回 · 2 重排（没挪就不重建；挪了只落新位，不重放入场） */
  function sigOf(k, L) { return [k, f1(L.C[0]), f1(L.C[1])].concat(L.slots.map(function (s) { return f1(s.ax) + ',' + f1(s.ay); })).join(' '); }
  function build(st, k, how) {
    var d = st.dots[k], P = F(), list = d.o.list && d.o.list.length ? d.o.list : [{ t: d.o.e.title, key: d.o.key }], n = list.length;
    if (how === 2 && last && last.k === k) { var L0 = layout(st, d, last.w); if (sigOf(k, L0) === last.sig) { dodge(L0.C, box); return; } }
    clear(); grp.setAttribute('class', 'skc-fan is-in' + (how === 1 ? ' is-quick' : how === 2 ? ' is-set' : ''));
    var els = list.map(function (it) { var t = mk('text', 'skc-fan-t', grp); t.textContent = short(it.t, P.chars); return t; });
    var ws = els.map(function (t) { return hk.txtW(t, 11); }), L = layout(st, d, ws), S = L.slots, C = L.C;
    last = { k: k, w: ws, sig: sigOf(k, L) };
    var shown = S.length >= n ? n : Math.max(0, S.length - 1), fb = null;
    els.forEach(function (t, i) { if (i >= shown) grp.removeChild(t); });
    function put(sl, el, i, cls) {
      var gi = mk('g', 'skc-fan-i' + cls, grp), dx = sl.ax - C[0], dy = sl.ay - C[1], l = Math.hypot(dx, dy) || 1, w = hk.txtW(el, 11), b = boxOf(sl, w);
      gi.style.setProperty('--i', String(i)); gi.style.setProperty('--fx', f1(-dx * 0.35) + 'px'); gi.style.setProperty('--fy', f1(-dy * 0.35) + 'px');
      at(mk('path', 'skc-fan-rib', gi), { pathLength: '1', d: 'M' + f1(C[0] + dx / l * (L.rb + 2)) + ' ' + f1(C[1] + dy / l * (L.rb + 2)) + 'L' + f1(sl.ax) + ' ' + f1(sl.ay) });
      gi.appendChild(el);
      at(el, sl.side ? { x: sl.ax + (sl.side > 0 ? 4 : -4), y: sl.ay + 4, 'text-anchor': sl.side > 0 ? 'start' : 'end' } : { x: sl.ax, y: sl.ay - 3, 'text-anchor': 'middle' });
      fb = fb ? [Math.min(fb[0], b[0]), Math.min(fb[1], b[1]), Math.max(fb[2], b[2]), Math.max(fb[3], b[3])] : b.slice();
    }
    for (var i = 0; i < shown; i++) put(S[i], els[i], i, list[i].key ? ' is-key' : '');
    if (n > shown && S[shown]) { var mo = mk('text', 'skc-fan-more', grp); mo.textContent = '+' + (n - shown); put(S[shown], mo, shown, ' is-more'); }
    box = fb; dodge(C, fb);
  }
  /* 悬停卡片让到扇面旁：右 → 左 → 上，都放不下就留原位 */
  function dodge(C, fb) {
    var c = svg.card; if (!c || c.hidden || !fb) return;
    var w = c.offsetWidth, h = c.offsetHeight, W = g.innerWidth, H = g.innerHeight, list = [[fb[2] + 14, C[1] - h - 12], [fb[0] - 14 - w, C[1] - h - 12], [C[0] - w / 2, fb[1] - 12 - h]];
    for (var i = 0; i < list.length; i++) {
      var x = Math.max(12, Math.min(W - 12 - w, list[i][0])), y = Math.max(76, list[i][1]);
      if (y + h <= H - 8 && !hit([x, y, x + w, y + h], fb, 4)) { c.style.setProperty('--sc-x', x.toFixed(0) + 'px'); c.style.setProperty('--sc-y', y.toFixed(0) + 'px'); return; }
    }
  }

  function open(k) {
    var st = hk && hk.state(); if (!st || !grp || !st.dots[k] || k === cur) return;
    var quick = now() - at0 < F().quick;   /* 扫带子 / 珠间移动：免交错动画 */
    cur = keyK = k; at0 = now();
    build(st, k, quick ? 1 : 0);
    svg.classList.add('skc-fanning');
  }
  function close() {
    if (cur < 0 || !grp) return;
    cur = -1; at0 = now(); box = null;
    grp.setAttribute('class', 'skc-fan is-out'); svg.classList.remove('skc-fanning');
  }
  function relayout() {
    var st = hk && hk.state(); if (!st) return;
    if (st.bandHit && !st.bandHit.hasAttribute('tabindex')) at(st.bandHit, { tabindex: '-1', 'aria-label': '因果密度带 · ←/→ 逐回' });
    if (cur >= 0 && st.dots[cur]) build(st, cur, 2);
  }
  function reset() { cur = keyK = -1; box = last = null; if (grp) { clear(); grp.setAttribute('class', 'skc-fan'); } if (svg) svg.classList.remove('skc-fanning'); }

  /* ── 键盘：珠 / 带子持焦时截下方向键、Enter、Esc（窗口捕获阶段，先于壳层的旋转） ── */
  function shownNear(st, k, dir) {
    for (var j = k + dir; j >= 0 && j < st.dots.length; j += dir) { var e = st.dots[j].el; if (e && e.getAttribute('visibility') !== 'hidden') return j; }
    return k;
  }
  function focusTo(st, k) {
    var d = st.dots[k]; if (!d) return;
    keyK = k;
    if (d.el && d.el.getAttribute('visibility') !== 'hidden') d.el.focus();
    else if (st.bandHit) { st.bandHit.focus(); st.bandK = k; }
    if (cur !== k) hk.lightEvent(k);
  }
  function onKey(e) {
    var st = hk && hk.state(), t = e.target, ev = st && t && t.closest ? t.closest('.sky-compass [data-ev], .sky-compass [data-band]') : null;
    if (!ev || e.altKey || e.ctrlKey || e.metaKey) return;
    var k = ev.hasAttribute('data-ev') ? +ev.getAttribute('data-ev') : Math.max(0, keyK), N = st.dots.length, to = null, key = e.key;
    if (key === 'ArrowLeft') to = k - 1; else if (key === 'ArrowRight') to = k + 1;
    else if (key === 'ArrowUp' || key === 'ArrowDown') to = shownNear(st, k, key === 'ArrowUp' ? -1 : 1);
    else if (key === 'Home') to = 0; else if (key === 'End') to = N - 1;
    else if (key === 'Tab' && !ev.hasAttribute('data-ev')) { to = shownNear(st, k, e.shiftKey ? -1 : 1); if (to === k) return; }   /* 带子持焦时 Tab 按回序跳到相邻的珠 */
    else if (key === 'Enter' || key === ' ') { if (cur !== k) hk.lightEvent(k); }
    else if (key !== 'Escape' || cur < 0) return;   /* 扇面已收：Esc 交还壳层（退出罗盘） */
    else hk.unlight();
    e.preventDefault(); e.stopImmediatePropagation();
    if (to !== null) focusTo(st, Math.max(0, Math.min(N - 1, to)));
  }
  g.addEventListener('keydown', onKey, true);
  function onFocus(e) {
    var ev = e.target && e.target.closest ? e.target.closest('[data-ev]') : null;
    if (ev && hk) { var k = +ev.getAttribute('data-ev'); keyK = k; if (cur !== k) hk.lightEvent(k); }
  }
  function onBlur(e) {
    var to = e.relatedTarget;
    if (to && to.closest && to.closest('.sky-compass [data-ev], .sky-compass [data-band]')) return;
    if (cur >= 0 && hk) hk.unlight();
  }

  function attach(s, h) {
    hk = h; if (svg === s) return;
    svg = s; grp = mk('g', 'skc-fan', svg); grp.setAttribute('aria-hidden', 'true');
    svg.addEventListener('focusin', onFocus); svg.addEventListener('focusout', onBlur);
  }

  g.CLSkyCompassFan = {
    attach: attach, open: open, close: close, relayout: relayout, reset: reset,
    stats: function () {
      var st = hk && hk.state(), d = st && cur >= 0 ? st.dots[cur] : null, mo = grp ? grp.querySelector('.skc-fan-more') : null;
      return { open: cur >= 0, k: cur, n: d ? d.o.count || 1 : 0, shown: grp && cur >= 0 ? grp.querySelectorAll('.skc-fan-i:not(.is-more)').length : 0,
        more: mo && cur >= 0 ? +mo.textContent.slice(1) : 0, box: box ? box.map(Math.round) : null };
    }
  };
})(window);
