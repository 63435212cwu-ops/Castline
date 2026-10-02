/**
 * @role component
 * @owns js/annulus/annulus-core.js
 * @budget dom≤160; js_ms≤0.6/frame（几何帧只写星 transform 与弧路径；静帧只写呼吸 opacity）
 * @contract v90
 * v90 F1 年轮星核：盘心 = 全书核心人物（阵营扇区 · 八芒属性星芒 · 咖位星等）+ 计数星徽 + 世界字形环。
 * 自注册 CLAnnulusSVG.use({name:'core'})；导出 window.CLAnnulusCore。
 * 纪律：
 *  - 盘面坐标只经 ctx.projectXY；本模块由四角投影求出同一张单应矩阵及其逆，用于屏幕度量、反投影与包含判定。
 *  - 分值只取 CLGemModel.build(c, G, {}) 的 attr[i].known/score（与双晶同源同口径）；未知 = 8px 处空心点，绝不画 0 长芒。
 *  - 人数超上限合成一枚 +N 聚合星，shown + N = 角色总数；阵营色取 NCConstellation.layout 的 cp.color（星域 camp-halo 同源），
 *    缺失再回落 CLPalette.campCss(stance)。
 *  - 布局状态是盘面坐标；间距度量用真实投影（屏幕 px）。只在挂载、视口变化或当前布局失效（重叠/越界）时重解，
 *    解算固定迭代、从确定性种子冷启动 → 同一投影下结果可复现。
 *  - 不写图谱、不调模型、不私开 rAF；呼吸只读 ctx.breath。
 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var FIELD = '散星';
  var CORE_K = 0.80, LIMIT_K = 0.86, BADGE_K = 0.20, R0_K = 0.30, RS_K = 0.60;
  var SOLVE_IT = 64, SAFE = 0.965, VALID = 0.997, GAP = 3;
  var CAMP_GAP = 0.10;
  var SIDES = ['below', 'above', 'right', 'left'];
  var MORE_SIDES = ['right', 'left', 'below', 'above'];
  var WORLD = [
    { key: 'locations', name: '地点', shape: 'M-3.5 -3.5H3.5V3.5H-3.5Z' },
    { key: 'items', name: '物品', shape: 'M0 -4.6L4.6 0L0 4.6L-4.6 0Z' },
    { key: 'worldRules', name: '规则', shape: 'M0 -4.4L4.18 -1.36L2.59 3.56H-2.59L-4.18 -1.36Z' },
    { key: 'clues', name: '伏笔', shape: 'M0 -5L1.2 -1.2L5 0L1.2 1.2L0 5L-1.2 1.2L-5 0L-1.2 -1.2Z' },
    { key: 'causeEdges', name: '因果', shape: 'M-4.6 0H4.2M1.4 -2.8L4.4 0L1.4 2.8' }
  ];
  var S = null;
  var live = { listeners: 0, mounts: 0, unmounts: 0 };

  /* ───────────────────────── 小工具 ───────────────────────── */
  function nowMs() { return (window.performance && typeof performance.now === 'function') ? performance.now() : 0; }
  function mk(tag, cls, parent) {
    var n = document.createElementNS(NS, tag);
    if (cls) n.setAttribute('class', cls);
    if (parent) parent.appendChild(n);
    return n;
  }
  function setA(el, k, v) {
    v = String(v);
    var c = el.__clCore || (el.__clCore = {});
    if (c[k] === v) return;
    c[k] = v; el.setAttribute(k, v);
    if (S) S.writes++;
  }
  function setCls(el, c, on) {
    if (!el || !el.classList) return;
    var has = el.classList.contains(c);
    if (on && !has) el.classList.add(c); else if (!on && has) el.classList.remove(c);
  }
  function tokPx(name, fb) {
    try {
      var v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
      return isFinite(v) && v > 0 ? v : fb;
    } catch (e) { return fb; }
  }
  function r1(v) { return Math.round(v * 10) / 10; }
  function r2(v) { return Math.round(v * 100) / 100; }
  function isFin(v) { return typeof v === 'number' && isFinite(v); }
  function clamp(x, a, b) { return x < a ? a : (x > b ? b : x); }
  function hexCss(n) { var s = (n >>> 0).toString(16); while (s.length < 6) s = '0' + s; return '#' + s.slice(-6); }
  function estW(s, fs, ls) {
    var w = 0, i, cc;
    s = String(s || '');
    for (i = 0; i < s.length; i++) {
      cc = s.charCodeAt(i);
      w += (cc > 0x2e7f || cc === 0x2026) ? fs : (cc === 0x20 ? fs * 0.3 : fs * 0.58);
    }
    return w + (ls || 0) * fs * s.length;
  }
  function graph() { try { return window.CLApp && typeof CLApp.graph === 'function' ? CLApp.graph() : null; } catch (e) { return null; } }
  function story() { try { return window.CLApp && typeof CLApp.story === 'function' ? CLApp.story() : null; } catch (e) { return null; } }
  function capFor(far) {
    var w = window.innerWidth || 1440, k = w <= 480 ? 6 : (w <= 900 ? 8 : 12);
    if (far) k = Math.max(6, k - 2);
    return k;
  }
  function prefersReduced() {
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }

  /* ───────────────────────── 单应矩阵（与 ctx.projectXY 同一平面投影） ───────────────────────── */
  function hom(ctx, R) {
    if (!ctx || typeof ctx.projectXY !== 'function' || !(R > 0)) return null;
    var p0 = ctx.projectXY(-R, -R), p1 = ctx.projectXY(R, -R), p2 = ctx.projectXY(R, R), p3 = ctx.projectXY(-R, R);
    if (!p0 || !p1 || !p2 || !p3) return null;
    var x0 = p0[0], y0 = p0[1], x1 = p1[0], y1 = p1[1], x2 = p2[0], y2 = p2[1], x3 = p3[0], y3 = p3[1];
    if (!isFin(x0 + y0 + x1 + y1 + x2 + y2 + x3 + y3)) return null;
    var dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3, dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
    var g = 0, h = 0;
    if (Math.abs(dx3) + Math.abs(dy3) > 1e-9) {
      var den = dx1 * dy2 - dx2 * dy1;
      if (Math.abs(den) < 1e-12) return null;
      g = (dx3 * dy2 - dx2 * dy3) / den; h = (dx1 * dy3 - dx3 * dy1) / den;
    }
    var a = x1 - x0 + g * x1, b = x3 - x0 + h * x3, c = x0, d = y1 - y0 + g * y1, e = y3 - y0 + h * y3, f = y0, k = 1 / (2 * R);
    var m = [a * k, b * k, (a + b) * 0.5 + c, d * k, e * k, (d + e) * 0.5 + f, g * k, h * k, (g + h) * 0.5 + 1];
    var inv = inv3(m);
    return inv ? { m: m, inv: inv, c: [x0, y0, x1, y1, x2, y2, x3, y3] } : null;
  }
  function inv3(m) {
    var a = m[0], b = m[1], c = m[2], d = m[3], e = m[4], f = m[5], g = m[6], h = m[7], i = m[8];
    var A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
    var det = a * A + b * B + c * C;
    if (!isFin(det) || Math.abs(det) < 1e-18) return null;
    var s = 1 / det;
    return [A * s, -(b * i - c * h) * s, (b * f - c * e) * s, B * s, (a * i - c * g) * s, -(a * f - c * d) * s,
      C * s, -(a * h - b * g) * s, (a * e - b * d) * s];
  }
  function ap(m, x, y) {
    var w = m[6] * x + m[7] * y + m[8];
    return [(m[0] * x + m[1] * y + m[2]) / w, (m[3] * x + m[4] * y + m[5]) / w];
  }
  function toS(x, y) { return ap(S.H.m, x, y); }
  function polar(r, a) { return ap(S.H.m, r * Math.cos(a), r * Math.sin(a)); }
  function planeR(x, y) { var q = ap(S.H.inv, x, y); return Math.sqrt(q[0] * q[0] + q[1] * q[1]); }

  /* ───────────────────────── 数据（只读图谱） ───────────────────────── */
  function tierOf(c) {   /* 咖位三档：阈值与 scene-camp-halo tierOf 前三档一致 */
    var imp = +c.importance || 0;
    if (c.role === '主角' || imp >= 78) return 0;
    if (c.role === '反派' || c.role === '核心配角' || imp >= 55) return 1;
    return 2;
  }
  /* 阵营色：与 scene-camp-halo 相同调用（NCConstellation.layout → cp.color，立场派生同一规则） */
  function haloTier(c) {
    var imp = (c && c.importance) || 0;
    if (c && c.role === '主角') return 0;
    if (imp >= 78) return 0;
    if (c && (c.role === '反派' || c.role === '核心配角')) return 1;
    if (imp >= 55) return 1;
    if (imp >= 30) return 2;
    return 3;
  }
  function haloWeight(c) { return ((c && c.importance) || 0) + (c && c.role === '主角' ? 70 : (c && (c.role === '反派' || c.role === '核心配角')) ? 34 : 0); }
  function campColors(G) {
    var out = {}, NC = window.NCConstellation, P = window.CLPalette;
    try {
      if (NC && typeof NC.layout === 'function') {
        var lay = NC.layout(G.characters || [], G.relations || [], G.camps || [], haloTier, haloWeight);
        (lay && lay.camps || []).forEach(function (cp) { if (cp && cp.name != null && isFin(cp.color)) out[String(cp.name)] = hexCss(cp.color); });
      }
    } catch (e) { /* 取色失败只回落，不阻断 */ }
    (G.camps || []).forEach(function (cp) {
      if (cp && cp.name && !out[cp.name] && P && typeof P.campCss === 'function') out[cp.name] = P.campCss(cp.stance);
    });
    if (!out[FIELD] && P && typeof P.campCss === 'function') out[FIELD] = P.campCss('');
    return out;
  }
  function gemOf(c, G) {
    var M = window.CLGemModel, m = null, rays = [], unk = [], i, a, t, L;
    try { m = M && typeof M.build === 'function' ? M.build(c, G, {}) : null; } catch (e) { m = null; }
    for (i = 0; i < 8; i++) {
      a = m && m.ok && m.attr ? m.attr[i] : null;
      t = i * Math.PI / 4;
      if (a && a.known === true && isFin(a.score)) {
        L = 4 + 12 * clamp(a.score, 0, 100) / 100;
        rays.push({ i: i, key: a.key, score: a.score, L: L, x: Math.sin(t) * L, y: -Math.cos(t) * L });
      } else {
        unk.push({ i: i, key: a ? a.key : null, x: Math.sin(t) * 8, y: -Math.cos(t) * 8 });
      }
    }
    return { rays: rays, unk: unk, ok: !!(m && m.ok) };
  }
  function participation(A, G, want) {
    var evs = G.events || [], out = {}, n;
    for (n in want) out[n] = [];
    (A.rings || []).forEach(function (r) {
      if (!r || !r.valid) return;
      var hit = {}, ro = r.roster || {}, k, e, cs;
      if (ro.lead && want[ro.lead]) hit[ro.lead] = 1;
      (ro.core || []).forEach(function (nm) { if (want[nm]) hit[nm] = 1; });
      (r.events || []).forEach(function (x) {
        e = x ? evs[x.ev] : null; cs = e && e.characters;
        if (cs) for (k = 0; k < cs.length; k++) if (want[cs[k]]) hit[cs[k]] = 1;
      });
      for (k in hit) out[k].push(String(r.id));
    });
    return out;
  }
  function countsOf(A, G) {
    var ch = {}, n = 0, st = story();
    (G.events || []).forEach(function (e) { var c = e && e.chapter; if (c != null && c !== '' && !ch[c]) { ch[c] = 1; n++; } });
    var th = st && st.threads ? st.threads.length : (A.aggregate ? A.aggregate.raw : (A.rings || []).length);
    return { ch: n, ev: (G.events || []).length, th: th, ppl: (G.characters || []).length };
  }
  function worldOf(G) {
    var caps = G.capabilities || {}, cov = (G.meta && G.meta.coverage) || {}, out = [];
    WORLD.forEach(function (w) {
      var rows = G[w.key], n = Array.isArray(rows) ? rows.length : 0;
      if (!(n > 0)) return;
      var cap = caps[w.key], cv = cov[w.key];
      var partial = !!((cap && (cap.status === 'partial' || cap.partial === true || cap.complete === false)) ||
        (cv && (cv.status === 'partial' || cv.partial === true || cv.complete === false)));
      out.push({ key: w.key, name: w.name, shape: w.shape, n: n, partial: partial });
    });
    return out;
  }

  /* ───────────────────────── 挂载：模型 + 种子 + DOM ───────────────────────── */
  function topAngle() {
    var best = 0, by = Infinity, i, a, q;
    for (i = 0; i < 72; i++) { a = i * Math.PI / 36; q = polar(S.rCore, a); if (q[1] < by) { by = q[1]; best = a; } }
    return best;
  }
  function centerOut(m) {
    var idx = [], c = (m - 1) / 2, i;
    for (i = 0; i < m; i++) idx.push(i);
    idx.sort(function (a, b) { return (Math.abs(a - c) - Math.abs(b - c)) || (a - b); });
    return idx;
  }
  function buildModel(ctx, G) {
    var A = ctx.A, chars = G.characters || [], i;
    var rs = (A.rings || []).filter(function (r) { return r && r.valid && isFin(r.r) && r.r > 0; }).map(function (r) { return r.r; });
    S.rIn = rs.length ? Math.min.apply(null, rs) : (A.R || 100) * 0.55;
    S.rCore = CORE_K * S.rIn; S.limit = LIMIT_K * S.rIn;
    S.cap = capFor(!!ctx.far); S.far = !!ctx.far;
    var order = [];
    for (i = 0; i < chars.length; i++) if (chars[i] && chars[i].name) order.push({ c: chars[i], i: i });
    order.sort(function (a, b) { return ((+b.c.importance || 0) - (+a.c.importance || 0)) || (a.i - b.i); });
    var shown = order.slice(0, Math.min(S.cap, order.length));
    S.total = chars.length; S.shownN = shown.length; S.more = S.total - S.shownN;
    var byCamp = {}, campOrder = [];
    (G.camps || []).forEach(function (cp) {
      if (!cp || !cp.name) return;
      campOrder.push(String(cp.name));
      (cp.members || []).forEach(function (m) { if (byCamp[m] == null) byCamp[m] = String(cp.name); });
    });
    var colors = campColors(G), want = {}, camps = {}, list = [];
    S.nodes = [];
    shown.forEach(function (o, rank) {
      var c = o.c, nm = String(c.name), cn = byCamp[nm] || String(c.camp || '').trim();
      if (!cn || cn === FIELD) cn = FIELD;
      var gm = gemOf(c, G), tier = tierOf(c), cr = [4.2, 3.4, 2.7][tier];
      var nd = { name: nm, rank: rank, tier: tier, campName: cn, cr: cr, gr: cr * 2.6, rays: gm.rays, unk: gm.unk,
        label: nm.length > 4 ? nm.slice(0, 3) + '…' : nm, fs: tier === 0 ? S.fsHi : S.fs, pts: {}, lit: [], more: false };
      var rb = { l: cr, r: cr, t: cr, b: cr };
      gm.rays.forEach(function (r) { rb.l = Math.max(rb.l, -r.x); rb.r = Math.max(rb.r, r.x); rb.t = Math.max(rb.t, -r.y); rb.b = Math.max(rb.b, r.y); });
      gm.unk.forEach(function (u) { rb.l = Math.max(rb.l, -u.x + 1.5); rb.r = Math.max(rb.r, u.x + 1.5); rb.t = Math.max(rb.t, -u.y + 1.5); rb.b = Math.max(rb.b, u.y + 1.5); });
      nd.rb = rb;
      want[nm] = 1;
      if (!camps[cn]) {
        camps[cn] = { name: cn, color: colors[cn] || null, members: [], weight: 0, idx: cn === FIELD ? 1e6 : (campOrder.indexOf(cn) < 0 ? 1e5 + list.length : campOrder.indexOf(cn)) };
        list.push(camps[cn]);
      }
      camps[cn].members.push(nd); camps[cn].weight += (+c.importance || 0) + 1;
      nd.color = camps[cn].color;
      S.nodes.push(nd);
    });
    var lit = participation(A, G, want);
    S.nodes.forEach(function (nd) {
      nd.lit = lit[nd.name] || [];
      nd.aria = nd.name + ' · ' + nd.campName + ' · 参与 ' + nd.lit.length + ' 条线 · 已知属性 ' + nd.rays.length + '/8';
      nd.stagger = S.shownN > 1 ? Math.round(7 * nd.rank / (S.shownN - 1)) : 0;
    });
    S.camps = list;
    if (S.more > 0) {
      S.moreNode = { name: '+' + S.more, more: true, rank: S.shownN, tier: 2, cr: 6.5, gr: 10, rays: [], unk: [],
        rb: { l: 7, r: 7, t: 7, b: 7 }, label: '+' + S.more, fs: S.fs, pts: {}, lit: [], stagger: 7, campName: '',
        aria: '其余 ' + S.more + ' 人 · 进入星域查看全部' };
      S.nodes.push(S.moreNode);
    } else S.moreNode = null;
    S.world = worldOf(G);
    S.counts = countsOf(A, G);
  }
  function buildSeeds() {
    var K = Math.max(1, S.shownN), camps = S.camps, m = camps.length, i, j;
    /* 顶部（远端，最扁）留给 +N / 世界字形；最重的阵营落在正下方（近端，最宽），其余左右交替 */
    var needPx = 0;
    S.world.forEach(function (w) { w.tw = estW(String(w.n), S.fs); needPx += 14 + w.tw + 10; });
    if (S.more > 0) needPx = Math.max(needPx, 46);
    var q1 = polar(S.rCore, S.aTop + 0.05), q2 = polar(S.rCore, S.aTop - 0.05);
    var ppr = Math.max(1, Math.sqrt((q1[0] - q2[0]) * (q1[0] - q2[0]) + (q1[1] - q2[1]) * (q1[1] - q2[1])) / 0.1);
    S.extraW = needPx > 0 ? clamp(needPx / ppr, 0.34, 1.7) : 0;
    if (!m) { S.campSeq = []; } else {
      var sorted = camps.slice().sort(function (a, b) { return (b.weight - a.weight) || (a.idx - b.idx); });
      var seq = new Array(m), mid = Math.floor((m - 1) / 2), offs = [0], d, oi = 0, pos;
      for (d = 1; offs.length < 2 * m + 2; d++) { offs.push(d); offs.push(-d); }
      for (i = 0; i < m; i++) {
        while (oi < offs.length) { pos = mid + offs[oi++]; if (pos >= 0 && pos < m && !seq[pos]) { seq[pos] = sorted[i]; break; } }
      }
      var gaps = S.extraW > 0 ? m + 1 : m;
      var avail = 2 * Math.PI - S.extraW - CAMP_GAP * gaps;
      var shares = seq.map(function (cp) { return avail * cp.members.length / K; });
      var minS = Math.min(0.42, avail / m), pass, deficit, big;
      for (pass = 0; pass < 4; pass++) {
        deficit = 0; big = 0;
        for (i = 0; i < m; i++) { if (shares[i] < minS) { deficit += minS - shares[i]; shares[i] = minS; } else big += shares[i]; }
        if (deficit < 1e-9 || !(big > 0)) break;
        for (i = 0; i < m; i++) if (shares[i] > minS) shares[i] -= deficit * shares[i] / big;
      }
      var a = S.aTop - (S.extraW > 0 ? S.extraW / 2 + CAMP_GAP : CAMP_GAP / 2);
      for (i = 0; i < m; i++) {
        var cp = seq[i], mk = cp.members.length, slots = centerOut(mk);
        cp.a0 = a; cp.a1 = a - shares[i]; a = cp.a1 - CAMP_GAP;
        for (j = 0; j < mk; j++) {
          var nd = cp.members[j], t = (slots[j] + 0.5) / mk, ang = cp.a0 - shares[i] * (0.08 + 0.84 * t);
          var rr = S.rCore * (R0_K + RS_K * nd.rank / K);
          nd.seed = [rr * Math.cos(ang), rr * Math.sin(ang)];
        }
      }
      S.campSeq = seq;
    }
    if (S.moreNode) { var rm = S.rCore * (S.world.length ? 0.56 : 0.62); S.moreNode.seed = [rm * Math.cos(S.aTop), rm * Math.sin(S.aTop)]; }
    var nw = S.world.length;
    S.world.forEach(function (w, k) { w.r = S.rCore * 0.94; w.a = S.aTop + S.extraW / 2 - S.extraW * (k + 0.5) / nw; });
  }
  function glyphSymbol(kind, id, defs) {
    var GL = window.CLAtlasGlyphs;
    if (!GL || typeof GL.defs !== 'function' || typeof DOMParser === 'undefined') return false;
    try {
      var src = GL.defs(), m = new RegExp('<symbol id="cl-g-' + kind + '"[\\s\\S]*?<\\/symbol>').exec(src);
      if (!m) return false;
      var doc = new DOMParser().parseFromString('<svg xmlns="' + NS + '">' + m[0].replace('id="cl-g-' + kind + '"', 'id="' + id + '"') + '</svg>', 'image/svg+xml');
      var sym = doc.documentElement && doc.documentElement.firstElementChild;
      if (!sym || sym.nodeName !== 'symbol') return false;
      defs.appendChild(document.importNode(sym, true));
      return true;
    } catch (e) { return false; }
  }
  function glyphUse(parent, id, ok, size) {
    if (!ok) { var c = mk('circle', 'cl-ann-core__glyph-fb', parent); c.setAttribute('r', String(size / 4)); return c; }
    var u = mk('use', 'cl-ann-core__glyph', parent);
    u.setAttribute('href', '#' + id);
    u.setAttribute('x', String(-size / 2)); u.setAttribute('y', String(-size / 2));
    u.setAttribute('width', String(size)); u.setAttribute('height', String(size));
    return u;
  }
  function raysD(nd) {
    var d = '';
    nd.rays.forEach(function (r) { d += 'M0 0L' + r2(r.x) + ' ' + r2(r.y); });
    return d;
  }
  function unkD(nd) {
    var d = '', rr = 1.4;
    nd.unk.forEach(function (u) {
      d += 'M' + r2(u.x + rr) + ' ' + r2(u.y) + 'A' + rr + ' ' + rr + ' 0 1 0 ' + r2(u.x - rr) + ' ' + r2(u.y) +
        'A' + rr + ' ' + rr + ' 0 1 0 ' + r2(u.x + rr) + ' ' + r2(u.y);
    });
    return d;
  }
  function buildDom(ctx) {
    var svg = ctx.svg, before = (ctx.groups && ctx.groups.chapters && ctx.groups.chapters.parentNode === svg) ? ctx.groups.chapters : null;
    var g = document.createElementNS(NS, 'g');
    g.setAttribute('class', 'cl-ann-g-core' + (S.low ? ' is-low' : '') + (S.still ? ' is-still' : ''));
    if (before) svg.insertBefore(g, before); else svg.appendChild(g);
    S.g = g;
    var defs = mk('defs', null, g), grad = mk('radialGradient', null, defs);
    grad.setAttribute('id', 'cl-ann-core-glow');
    var s0 = mk('stop', 'cl-ann-core__gs0', grad), s1 = mk('stop', 'cl-ann-core__gs1', grad);
    s0.setAttribute('offset', '0'); s1.setAttribute('offset', '1');
    var okCore = glyphSymbol('core', 'cl-ann-core-sym-core', defs);
    var okAgg = S.moreNode ? glyphSymbol('aggregate', 'cl-ann-core-sym-agg', defs) : false;
    /* 阵营扇区弧 + 弧名 */
    var gC = mk('g', 'cl-ann-core__camps cl-ann-core__fade', g);
    (S.campSeq || []).forEach(function (cp, k) {
      var p = mk('path', 'cl-ann-core__arc', gC), id = 'cl-ann-core-cp-' + k;
      p.setAttribute('id', id); p.setAttribute('d', '');
      if (cp.color) p.setAttribute('stroke', cp.color);
      var t = mk('text', 'cl-ann-core__camp', gC), tp = mk('textPath', null, t);
      if (cp.color) t.setAttribute('fill', cp.color);
      t.setAttribute('text-anchor', 'middle'); t.setAttribute('aria-hidden', 'true');
      tp.setAttribute('href', '#' + id); tp.setAttribute('startOffset', '50%');
      cp.el = { path: p, text: t, tp: tp }; cp.shownText = null;
    });
    /* 世界字形环（只画有记录的类别；partial 虚线） */
    if (S.world.length) {
      var gW = mk('g', 'cl-ann-core__world cl-ann-core__fade', g);
      S.world.forEach(function (w) {
        var wg = mk('g', 'cl-ann-core__wi' + (w.partial ? ' is-partial' : ''), gW);
        wg.setAttribute('data-world', w.key); wg.setAttribute('role', 'img');
        wg.setAttribute('aria-label', w.name + ' ' + w.n + ' 条' + (w.partial ? '（部分）' : ''));
        var sp = mk('path', 'cl-ann-core__wshape', wg); sp.setAttribute('d', w.shape);
        var tx = mk('text', 'cl-ann-core__wn', wg); tx.setAttribute('x', '8'); tx.setAttribute('y', '3.5'); tx.textContent = String(w.n);
        w.el = { g: wg, text: tx };
      });
    }
    /* 计数星徽 */
    var gB = mk('g', 'cl-ann-core__badge cl-ann-core__fade', g);
    gB.setAttribute('role', 'img');
    var C = S.counts;
    gB.setAttribute('aria-label', '全书 ' + C.ch + ' 章 · ' + C.ev + ' 事件 · ' + C.th + ' 线 · ' + C.ppl + ' 人');
    var hub = mk('g', 'cl-ann-core__hub', gB);
    glyphUse(hub, 'cl-ann-core-sym-core', okCore, 16);
    S.badge = { g: gB, hub: hub, halves: [] };
    S.countTxt = [C.ch + ' 章 · ' + C.ev + ' 事件', C.th + ' 线 · ' + C.ppl + ' 人'];
    S.countTxtC = [C.ch + '章·' + C.ev + '事件', C.th + '线·' + C.ppl + '人'];
    for (var h = 0; h < 2; h++) {
      var bp = mk('path', 'cl-ann-core__ring', gB), bid = 'cl-ann-core-bp-' + h;
      bp.setAttribute('id', bid); bp.setAttribute('d', '');
      var bt = mk('text', 'cl-ann-core__count', gB), btp = mk('textPath', null, bt);
      bt.setAttribute('text-anchor', 'middle'); bt.setAttribute('aria-hidden', 'true');
      btp.setAttribute('href', '#' + bid); btp.setAttribute('startOffset', '50%');
      S.badge.halves.push({ path: bp, text: bt, tp: btp, shown: null });
    }
    /* 星 */
    var gS = mk('g', 'cl-ann-core__stars', g);
    S.nodes.forEach(function (nd) {
      var sg = mk('g', 'cl-ann-core__star' + (nd.more ? ' is-more' : ' is-t' + nd.tier), gS);
      sg.setAttribute('tabindex', '0'); sg.setAttribute('role', 'button');
      sg.setAttribute('aria-label', nd.aria); sg.setAttribute('data-stagger', String(nd.stagger));
      if (nd.more) sg.setAttribute('data-core-more', String(S.more)); else sg.setAttribute('data-core-name', nd.name);
      var glow = mk('circle', 'cl-ann-core__glow', sg); glow.setAttribute('r', String(r1(nd.gr)));
      var el = { g: sg, glow: glow };
      if (nd.more) {
        el.glyph = glyphUse(sg, 'cl-ann-core-sym-agg', okAgg, 14);
      } else {
        el.rays = mk('path', 'cl-ann-core__rays', sg); el.rays.setAttribute('d', raysD(nd));
        el.rays.setAttribute('data-rays', String(nd.rays.length));
        el.unk = mk('path', 'cl-ann-core__unk', sg); el.unk.setAttribute('d', unkD(nd));
        el.unk.setAttribute('data-unknown', String(nd.unk.length));
        el.dot = mk('circle', 'cl-ann-core__dot', sg); el.dot.setAttribute('r', String(nd.cr));
        el.dot.setAttribute('fill', nd.color || 'var(--cl-ann-core-gold)');
      }
      el.name = mk('text', 'cl-ann-core__name' + (nd.tier === 0 && !nd.more ? ' is-hi' : ''), sg);
      el.name.setAttribute('text-anchor', 'middle');
      el.name.textContent = nd.label;
      nd.el = el; nd.side = undefined;
    });
    /* 悬停短签：放在最顶层，不被外环压住 */
    var tipG = document.createElementNS(NS, 'g');
    tipG.setAttribute('class', 'cl-ann-g-core-tip');
    tipG.setAttribute('aria-hidden', 'true');
    svg.appendChild(tipG);
    S.tipG = tipG;
    S.tip = { g: tipG, bg: mk('rect', 'cl-ann-core__tipbg', tipG), text: mk('text', 'cl-ann-core__tiptx', tipG), w: 0 };
    S.tip.bg.setAttribute('rx', '3');
  }
  function measureLabels() {
    S.nodes.forEach(function (nd) {
      var bb = null;
      try { bb = nd.el.name.getBBox(); } catch (e) { bb = null; }
      if (bb && bb.width > 0 && bb.height > 0) { nd.lw = bb.width + 2; nd.lh = bb.height; nd.lasc = -bb.y; }
      else { nd.lw = estW(nd.label, nd.fs) + 2; nd.lh = nd.fs * 1.3; nd.lasc = nd.fs * 0.95; }
      nd.pts = {}; nd.side = undefined;
    });
  }
  function on(el, type, fn, opt) {
    el.addEventListener(type, fn, opt || false);
    S.bound.push([el, type, fn, opt || false]); live.listeners++;
  }

  /* ───────────────────────── 几何：盒子 / 包含 / 解算 ───────────────────────── */
  function labelBox(nd, mode, side) {
    var w = nd.lw, h = nd.lh, o;
    if (side === 'below') { o = (mode === 'clear' ? nd.rb.b : nd.cr) + 2; return [-w / 2, o, w / 2, o + h]; }
    if (side === 'above') { o = (mode === 'clear' ? nd.rb.t : nd.cr) + 2; return [-w / 2, -o - h, w / 2, -o]; }
    if (side === 'right') { o = (mode === 'clear' ? nd.rb.r : nd.cr) + 3; return [o, -h / 2, o + w, h / 2]; }
    o = (mode === 'clear' ? nd.rb.l : nd.cr) + 3; return [-o - w, -h / 2, -o, h / 2];
  }
  function prefSide(nd) { return nd.more ? 'right' : 'below'; }
  function hardBox(nd, mode) {
    var lb = labelBox(nd, mode, prefSide(nd)), c = nd.cr + 1;
    return [Math.min(lb[0], -c), Math.min(lb[1], -c), Math.max(lb[2], c), Math.max(lb[3], c)];
  }
  function ptsFor(nd, mode, side) {
    var key = mode + '|' + side;
    if (nd.pts[key]) return nd.pts[key];
    var p = [], i, a;
    nd.rays.forEach(function (r) { p.push([r.x, r.y]); });
    nd.unk.forEach(function (u) { var k = (8 + 2) / 8; p.push([u.x * k, u.y * k]); });   /* 空心点 r1.4 + 描边半宽 */
    for (i = 0; i < 12; i++) { a = i * Math.PI / 6; p.push([Math.cos(a) * nd.gr * 1.036, Math.sin(a) * nd.gr * 1.036]); }   /* 外接十二边形（1/cos15°）：光晕圆整体被包住 */
    if (side) { var b = labelBox(nd, mode, side); p.push([b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]); }
    nd.pts[key] = p;
    return p;
  }
  function worstR(s, pts) {
    var w = 0, i, rr;
    for (i = 0; i < pts.length; i++) { rr = planeR(s[0] + pts[i][0], s[1] + pts[i][1]); if (rr > w) w = rr; }
    return w;
  }
  function contain(s, pts, L) {
    var w = worstR(s, pts);
    if (w <= L) return false;
    var c = S.cS, k = 1 - (1 - L / w) * 1.25;
    if (k < 0.5) k = 0.5;
    s[0] = c[0] + (s[0] - c[0]) * k; s[1] = c[1] + (s[1] - c[1]) * k;
    return true;
  }
  function absB(b, s) { return [s[0] + b[0], s[1] + b[1], s[0] + b[2], s[1] + b[3]]; }
  function inter(a, b) { return a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3]; }
  function hitList(b, list, skip) {
    for (var i = 0; i < list.length; i++) if (i !== skip && list[i] && inter(b, list[i])) return true;
    return false;
  }
  function boxInside(b, L) {
    return planeR(b[0], b[1]) <= L && planeR(b[2], b[1]) <= L && planeR(b[2], b[3]) <= L && planeR(b[0], b[3]) <= L;
  }
  /* 外环沿弧名：上半圈字形朝外、下半圈字形朝内（注解 ≤ 字号+描边）→ 星名盒外扩后仍须落在最内车道之内 */
  function arcSafe(b, k) {
    if (!isFinite(S.rLab)) return true;
    var L = S.rLab * (k || 0.995);
    return planeR(b[0] - 14, b[1] - 6) < L && planeR(b[2] + 14, b[1] - 6) < L && planeR(b[2] + 14, b[3] + 14) < L && planeR(b[0] - 14, b[3] + 14) < L;
  }
  function sepPair(si, sj, bi, bj, wi, wj, k) {
    var al = si[0] + bi[0], at = si[1] + bi[1], ar = si[0] + bi[2], ab = si[1] + bi[3];
    var cl = sj[0] + bj[0], ct = sj[1] + bj[1], cr = sj[0] + bj[2], cb = sj[1] + bj[3];
    var ox = Math.min(ar, cr) - Math.max(al, cl) + GAP, oy = Math.min(ab, cb) - Math.max(at, ct) + GAP;
    if (ox <= 0 || oy <= 0) return;
    var fi = wj / (wi + wj), fj = wi / (wi + wj), sx, sy;
    if (ox * 0.8 < oy) { sx = (al + ar) - (cl + cr) >= 0 ? 1 : -1; si[0] += sx * ox * fi * k; sj[0] -= sx * ox * fj * k; }
    else { sy = (at + ab) - (ct + cb) >= 0 ? 1 : -1; si[1] += sy * oy * fi * k; sj[1] -= sy * oy * fj * k; }
  }
  function pushOut(s, b, o) {
    var al = s[0] + b[0], at = s[1] + b[1], ar = s[0] + b[2], ab = s[1] + b[3];
    var ox = Math.min(ar, o[2]) - Math.max(al, o[0]) + GAP, oy = Math.min(ab, o[3]) - Math.max(at, o[1]) + GAP;
    if (ox <= 0 || oy <= 0) return;
    if (ox < oy) s[0] += ((al + ar) - (o[0] + o[2]) >= 0 ? 1 : -1) * ox;
    else s[1] += ((at + ab) - (o[1] + o[3]) >= 0 ? 1 : -1) * oy;
  }
  /* 标签优先级：咖位序，+N 聚合签紧跟首星（它承载守恒数字，窄，先放） */
  function priority() {
    var out = [], i, K = S.shownN;
    for (i = 0; i < K; i++) out.push(i);
    if (S.moreNode) out.splice(Math.min(1, K), 0, S.nodes.length - 1);
    return out;
  }
  /* 迟滞：解算包含 0.965·limit、分配 0.985、验收 0.997（径向）；分配相交判定外扩 1px、验收不外扩——
   * 相机慢漂的亚像素移动不会反复触发重解。径向不外扩像素：盘近端透视压缩，2% 半径不足 1px。 */
  function grow(b, m) { return [b[0] - m, b[1] - m, b[2] + m, b[3] + m]; }
  function assignSides(s, mode, labeled) {
    var N = S.nodes, placed = [], sides = [], fails = 0, L = S.limit * 0.985, i, k, pi;
    var cores = N.map(function (nd, j) { var c = nd.cr + 2; return [s[j][0] - c, s[j][1] - c, s[j][0] + c, s[j][1] + c]; });
    for (i = 0; i < N.length; i++) sides.push(null);
    for (pi = 0; pi < S.prio.length; pi++) {
      i = S.prio[pi];
      if (!labeled[i]) continue;
      var nd = N[i], pref = nd.more ? MORE_SIDES : SIDES, got = null, b = null;
      for (k = 0; k < pref.length && !got; k++) {
        var raw = absB(labelBox(nd, mode, pref[k]), s[i]);
        if (!boxInside(raw, L) || !arcSafe(raw, 0.985)) continue;
        b = grow(raw, 1);
        if (hitList(b, placed) || hitList(b, cores, i) || hitList(b, S.obst)) continue;
        got = pref[k];
      }
      if (got) placed.push(grow(absB(labelBox(nd, mode, got), s[i]), 1)); else fails++;
      sides[i] = got;
    }
    return { sides: sides, fails: fails };
  }
  function solveMode(mode, kLab) {
    var N = S.nodes, n = N.length, s = [], seed = [], hb = [], rbx = [], pts = [], wt = [], labeled = [], i, j, o, it, L = S.limit * SAFE, K = Math.max(1, S.shownN);
    for (i = 0; i < n; i++) labeled.push(false);
    for (i = 0; i < kLab && i < S.prio.length; i++) labeled[S.prio[i]] = true;
    for (i = 0; i < n; i++) {
      var q = toS(N[i].seed[0], N[i].seed[1]), c = N[i].cr + 2;
      s.push([q[0], q[1]]); seed.push(q);
      hb.push(labeled[i] ? hardBox(N[i], mode) : [-c, -c, c, c]);
      rbx.push([-N[i].rb.l, -N[i].rb.t, N[i].rb.r, N[i].rb.b]);
      pts.push(ptsFor(N[i], mode, labeled[i] ? prefSide(N[i]) : null));
      wt.push(N[i].more ? 1 : 1 + (K - N[i].rank) / K);
    }
    for (it = 0; it < SOLVE_IT; it++) {
      for (i = 0; i < n; i++) { s[i][0] += (seed[i][0] - s[i][0]) * 0.05; s[i][1] += (seed[i][1] - s[i][1]) * 0.05; }
      for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) sepPair(s[i], s[j], hb[i], hb[j], wt[i], wt[j], 0.6);
      for (i = 0; i < n; i++) for (j = 0; j < n; j++) if (i !== j) sepPair(s[i], s[j], rbx[i], hb[j], wt[i], wt[j], 0.18);
      for (i = 0; i < n; i++) for (o = 0; o < S.obst.length; o++) pushOut(s[i], hb[i], S.obst[o]);
      for (i = 0; i < n; i++) contain(s[i], pts[i], L);
    }
    for (it = 0; it < 30; it++) {
      var moved = false;
      for (i = 0; i < n; i++) if (contain(s[i], pts[i], L)) moved = true;
      if (!moved) break;
    }
    var res = assignSides(s, mode, labeled);
    return { s: s, sides: res.sides, fails: res.fails, mode: mode, k: kLab };
  }
  /* 先全部标注；放不下（手机盘心过小）才逐个退掉最低优先级的名字签——星本身与星芒永不删，名字在悬停短签与 aria 里 */
  function solveAll() {
    var total = S.prio.length, k, pick = null, r;
    S.trace = [];
    for (k = total; k >= 0 && !pick; k--) {
      r = solveMode('clear', k); S.trace.push('c' + k + ':' + r.fails);
      if (!r.fails) { pick = r; break; }
      r = solveMode('tight', k); S.trace.push('t' + k + ':' + r.fails);
      if (!r.fails) { pick = r; break; }
    }
    if (!pick) pick = solveMode('tight', 0);
    S.pos = pick.s.map(function (q) { return ap(S.H.inv, q[0], q[1]); });
    S.sides = pick.sides; S.mode = pick.mode; S.fails = total - pick.k; S.solves++;
    S.nodes.forEach(function (nd, i) {
      setA(nd.el.g, 'data-core-x', r2(S.pos[i][0])); setA(nd.el.g, 'data-core-y', r2(S.pos[i][1]));
    });
  }
  function validate() {
    var N = S.nodes, L = S.limit * VALID, lbs = [], cores = [], i, j, s;
    for (i = 0; i < N.length; i++) {
      s = toS(S.pos[i][0], S.pos[i][1]);
      if (!isFin(s[0]) || !isFin(s[1])) return false;
      if (worstR(s, ptsFor(N[i], S.mode, S.sides[i])) > L) return false;
      var c = N[i].cr + 1; cores.push([s[0] - c, s[1] - c, s[0] + c, s[1] + c]);
      if (S.aggBox && inter(cores[i], S.aggBox)) return false;
      if (S.sides[i]) {
        var b = absB(labelBox(N[i], S.mode, S.sides[i]), s);
        if (!arcSafe(b) || hitList(b, S.obst)) return false;
        lbs.push(b);
      } else lbs.push(null);
    }
    for (i = 0; i < N.length; i++) {
      if (!lbs[i]) continue;
      for (j = 0; j < N.length; j++) {
        if (j !== i && ((j > i && lbs[j] && inter(lbs[i], lbs[j])) || inter(lbs[i], cores[j]))) return false;
      }
    }
    return true;
  }

  /* ───────────────────────── 逐帧：弧 / 徽 / 字形 / 星 ───────────────────────── */
  function arcPts(r, a0, a1, step) {
    var n = clamp(Math.ceil(Math.abs(a1 - a0) / step) + 1, 3, 48), out = [], i, q;
    for (i = 0; i < n; i++) {
      q = polar(r, a0 + (a1 - a0) * i / (n - 1));
      if (!isFin(q[0]) || !isFin(q[1])) return null;
      out.push(q);
    }
    return out;
  }
  function upright(pts) {
    var mi = Math.max(1, pts.length >> 1);
    if (pts[mi][0] < pts[mi - 1][0]) { pts.reverse(); return true; }
    return false;
  }
  function dOf(pts) {
    var d = '', i;
    for (i = 0; i < pts.length; i++) d += (i ? 'L' : 'M') + r1(pts[i][0]) + ' ' + r1(pts[i][1]);
    return d;
  }
  function cumLen(pts) {
    var c = [0], i, dx, dy;
    for (i = 1; i < pts.length; i++) { dx = pts[i][0] - pts[i - 1][0]; dy = pts[i][1] - pts[i - 1][1]; c.push(c[i - 1] + Math.sqrt(dx * dx + dy * dy)); }
    return c;
  }
  function pointAt(pts, cum, d) {
    var i = 1;
    while (i < pts.length - 1 && cum[i] < d) i++;
    var seg = cum[i] - cum[i - 1] || 1, t = clamp((d - cum[i - 1]) / seg, 0, 1);
    return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t];
  }
  function fitText(name, avail, fs, ls) {
    if (estW(name, fs, ls) <= avail) return name;
    for (var k = name.length - 1; k >= 2; k--) { var t = name.slice(0, k) + '…'; if (estW(t, fs, ls) <= avail) return t; }
    return '';
  }
  function textObstacles(pts, cum, w, fs, dyOff, into) {
    var len = cum[cum.length - 1], from = (len - w) / 2, to = (len + w) / 2, step = fs * 0.8, d, p, nx, ny, nl, cx, cy, h = fs * 0.62, off = fs * 0.55 + dyOff;
    for (d = from; d <= to + 0.01; d += step) {
      p = pointAt(pts, cum, Math.min(d, to));
      nx = S.cS[0] - p[0]; ny = S.cS[1] - p[1]; nl = Math.sqrt(nx * nx + ny * ny) || 1;
      cx = p[0] + nx / nl * off; cy = p[1] + ny / nl * off;
      into.push([cx - h, cy - h, cx + h, cy + h]);
    }
  }
  function campsFrame() {
    var fs = S.fs, i;
    for (i = 0; i < S.campSeq.length; i++) {
      var cp = S.campSeq[i], pts = arcPts(S.rCore, cp.a0, cp.a1, Math.PI / 60);
      if (!pts) continue;
      var rev = upright(pts), cum = cumLen(pts), len = cum[cum.length - 1];
      setA(cp.el.path, 'd', dOf(pts));
      setA(cp.el.text, 'dominant-baseline', rev ? 'auto' : 'hanging');
      setA(cp.el.text, 'dy', rev ? '-3' : '3');
      var txt = S.campNamesOff ? '' : fitText(cp.name, len - 10, fs, 0.12);
      if (txt !== cp.shownText) { cp.shownText = txt; cp.el.tp.textContent = txt; setCls(cp.el.text, 'is-quiet', !txt); }
      if (txt) textObstacles(pts, cum, estW(txt, fs, 0.12), fs, 3, S.obstCamp);
    }
  }
  function badgeFrame() {
    var c = S.cS, rb = S.rCore * BADGE_K, h, box = [c[0] - 8, c[1] - 8, c[0] + 8, c[1] + 8];
    setA(S.badge.hub, 'transform', 'translate(' + r1(c[0]) + ' ' + r1(c[1]) + ')');
    var halves = [[S.aTop + Math.PI / 2, S.aTop - Math.PI / 2], [S.aTop - Math.PI / 2, S.aTop - 1.5 * Math.PI]];
    var geo = [], ls = 0.06, form = 'full';
    for (h = 0; h < 2; h++) {
      var pts = arcPts(rb, halves[h][0], halves[h][1], Math.PI / 24);
      if (!pts) { geo.push(null); continue; }
      var rev = upright(pts), cum = cumLen(pts), len = cum[cum.length - 1];
      geo.push({ pts: pts, rev: rev, len: len });
      /* 两半同一写法：任一半放不下全称，两半都用紧凑式；紧凑也放不下则整枚计数退场（只留中心字形） */
      if (form === 'full' && estW(S.countTxt[h], S.fs, ls) + 8 > len) form = 'compact';
      if (form === 'compact' && estW(S.countTxtC[h], S.fs, ls) + 8 > len) form = 'none';
    }
    for (h = 0; h < 2; h++) {
      var H = S.badge.halves[h], G2 = geo[h];
      if (!G2) continue;
      setA(H.path, 'd', dOf(G2.pts));
      setA(H.text, 'dominant-baseline', G2.rev ? 'auto' : 'hanging');
      setA(H.text, 'dy', G2.rev ? '-2' : '2');
      var txt = form === 'full' ? S.countTxt[h] : (form === 'compact' ? S.countTxtC[h] : '');
      /* 另一模块的「剧情星簇」聚合钮若压住这一半，这一半让开（不叠字） */
      if (txt && S.aggBox) {
        var hb = [Infinity, Infinity, -Infinity, -Infinity];
        G2.pts.forEach(function (q) { hb[0] = Math.min(hb[0], q[0]); hb[1] = Math.min(hb[1], q[1]); hb[2] = Math.max(hb[2], q[0]); hb[3] = Math.max(hb[3], q[1]); });
        if (inter([hb[0] - 6, hb[1] - 8, hb[2] + 6, hb[3] + 8], S.aggBox)) txt = '';
      }
      if (txt !== H.shown) { H.shown = txt; H.tp.textContent = txt; setCls(H.text, 'is-quiet', !txt); }
      if (txt) G2.pts.forEach(function (q) { box[0] = Math.min(box[0], q[0]); box[1] = Math.min(box[1], q[1]); box[2] = Math.max(box[2], q[0]); box[3] = Math.max(box[3], q[1]); });
    }
    S.badgeBox = [box[0] - 2, box[1] - 2, box[2] + 2, box[3] + 2];
    S.obst.push(S.badgeBox);
  }
  function worldFrame() {
    S.world.forEach(function (w) {
      var q = polar(w.r, w.a);
      setA(w.el.g, 'transform', 'translate(' + r1(q[0]) + ' ' + r1(q[1]) + ')');
      S.obst.push([q[0] - 6, q[1] - 6, q[0] + 9 + w.tw, q[1] + 6]);
    });
  }
  function applySide(nd, side) {
    if (nd.side === side && nd.sideMode === S.mode) return;
    nd.side = side; nd.sideMode = S.mode;
    setCls(nd.el.name, 'is-quiet', !side);
    if (!side) return;
    var b = labelBox(nd, S.mode, side);
    setA(nd.el.name, 'x', r1(side === 'right' ? b[0] + 1 : (side === 'left' ? b[2] - 1 : 0)));
    setA(nd.el.name, 'y', r1(b[1] + nd.lasc));
    setA(nd.el.name, 'text-anchor', side === 'right' ? 'start' : (side === 'left' ? 'end' : 'middle'));
  }
  function place() {
    var i, nd, q;
    for (i = 0; i < S.nodes.length; i++) {
      nd = S.nodes[i]; q = toS(S.pos[i][0], S.pos[i][1]); nd.s = q;
      setA(nd.el.g, 'transform', 'translate(' + r1(q[0]) + ' ' + r1(q[1]) + ')');
      applySide(nd, S.sides[i]);
    }
  }
  /* 外环当前真正可见的沿弧名所在的最内半径（手机端支线名整体 display:none，不该约束星核）。
   * 可见集签名不变就不重读样式；签名变了才对可见者各读一次 computed display。 */
  function labelRadius() {
    var labs = S.svg.querySelectorAll('.cl-ann-label[data-id]'), sig = String(window.innerWidth), vis = [], i, rmin = Infinity;
    for (i = 0; i < labs.length; i++) if (!labs[i].hasAttribute('hidden')) { vis.push(labs[i]); sig += ',' + labs[i].getAttribute('data-id'); }
    if (sig === S.labSig) return;
    S.labSig = sig;
    var vk = window.innerWidth + 'x' + window.innerHeight;
    if (S.labVK !== vk) { S.labVK = vk; S.labDisp = typeof WeakMap === 'function' ? new WeakMap() : null; }
    for (i = 0; i < vis.length; i++) {
      /* 媒体规则造成的 display:none 只随视口变：每个标签每个视口只读一次样式，避免在别的插件刚写完 DOM 的帧里反复强制样式重算 */
      var off = S.labDisp ? S.labDisp.get(vis[i]) : undefined;
      if (off === undefined) {
        var cs = getComputedStyle(vis[i]); S.styleReads++;
        off = cs.display === 'none' || cs.visibility === 'hidden';
        if (S.labDisp) S.labDisp.set(vis[i], off);
      }
      if (off) continue;
      var ring = S.ctx && typeof S.ctx.ringById === 'function' ? S.ctx.ringById(vis[i].getAttribute('data-id')) : null;
      if (ring && isFin(ring.r) && ring.r < rmin) rmin = ring.r;
    }
    S.rLab = rmin;
  }
  /* 年轮聚合钮 #atlasAggregate（别的模块所有，固定在视口中部）：可见时是星核的障碍。
   * 只在 hidden 状态或视口变化时读一次矩形，逐帧只读 .hidden 属性（不触发布局）。 */
  function aggregateObstacle() {
    var b = S.aggEl && S.aggEl.isConnected ? S.aggEl : (S.aggEl = document.getElementById('atlasAggregate'));
    var hid = b ? !!b.hidden : null;
    if (hid === S.aggHid && window.innerWidth === S.aggW && window.innerHeight === S.aggH && S.aggKey) return false;
    S.aggHid = hid; S.aggW = window.innerWidth; S.aggH = window.innerHeight; S.aggKey = true; S.aggBox = null;
    if (b && !b.hidden) {
      var cs = getComputedStyle(b);
      if (cs.display !== 'none' && cs.visibility !== 'hidden') {
        var r = b.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) S.aggBox = [r.left - 2, r.top - 2, r.right + 2, r.bottom + 2];
      }
    }
    return true;
  }
  /* 亚像素跳帧：参考四角（±rIn）相对上次落地的几何移动都 <0.2px 时整帧不算不写（相机慢漂每帧只动百分之几像素）。
   * 由此造成的滞后 ≤0.2px，远小于解算余量（包含 0.965 / 验收 0.997）与标签 1px 外扩。 */
  function nearlySame(a, b) {
    if (!a || !b) return false;
    for (var i = 0; i < 8; i++) if (Math.abs(a[i] - b[i]) >= 0.2) return false;
    return true;
  }
  function geometry(force) {
    var H = hom(S.ctx, S.rIn);
    if (!H) { setCls(S.g, 'is-off', true); S.lastC = null; return; }
    if (aggregateObstacle()) S.needSolve = true;
    if (!force && !S.needSolve && S.pos && nearlySame(H.c, S.lastC)) { S.skips++; return; }
    S.lastC = H.c;
    setCls(S.g, 'is-off', false);
    S.H = H; S.cS = toS(0, 0);
    S.obst = S.aggBox ? [S.aggBox] : []; S.obstCamp = [];
    if (S.needSolve || !S.pos || (S.geoApplied++ % 12) === 0) labelRadius();   /* 外环沿弧名可见集变化慢：解算帧 + 每 12 个落地几何帧查一次 */
    campsFrame(); badgeFrame(); worldFrame();
    S.obstBase = S.obst; S.obst = S.obstBase.concat(S.obstCamp);
    var why = !S.pos ? 'init' : (S.needSolve ? 'need' : '');
    S.sinceSolve++;
    /* 失效重解限频：距上次解算 ≥20 个几何帧；上次解本身就不满足（聚合钮压满盘心等不可解局面）则等投影移动 >6px 再试 */
    if (!why && S.sinceSolve >= 20 && !validate()) {
      var ref = polar(S.rCore, S.aTop), moved = S.solveRef ? Math.abs(ref[0] - S.solveRef[0]) + Math.abs(ref[1] - S.solveRef[1]) + Math.abs(S.cS[0] - S.solveRef[2]) + Math.abs(S.cS[1] - S.solveRef[3]) : 99;
      if (!S.unsat || moved > 6) why = 'invalid'; else S.why.held = (S.why.held || 0) + 1;
    }
    if (why) {
      S.why[why] = (S.why[why] || 0) + 1;
      /* 每次重解都先恢复阵营弧名再试；只有星名因此放不下时才让弧名退场 */
      if (S.campNamesOff) {
        S.campNamesOff = false; S.obstCamp = [];
        S.obst = S.aggBox ? [S.aggBox] : []; campsFrame(); badgeFrame(); worldFrame();
        S.obstBase = S.obst; S.obst = S.obstBase.concat(S.obstCamp);
      }
      solveAll();
      /* 盘心过小（手机）时阵营弧名会挤掉星名：星名优先，弧名退场（彩色扇区弧仍在） */
      if (S.fails > 0 && !S.campNamesOff && S.obstCamp.length) {
        var keep = { pos: S.pos, sides: S.sides, mode: S.mode, fails: S.fails };
        S.campNamesOff = true; S.obst = S.obstBase;
        solveAll();
        if (S.fails < keep.fails) { S.obstCamp = []; campsFrame(); }
        else { S.campNamesOff = false; S.obst = S.obstBase.concat(S.obstCamp); S.pos = keep.pos; S.sides = keep.sides; S.mode = keep.mode; S.fails = keep.fails; }
      }
      S.needSolve = false; S.sinceSolve = 0;
      var rp = polar(S.rCore, S.aTop); S.solveRef = [rp[0], rp[1], S.cS[0], S.cS[1]];
      S.unsat = !validate();
    }
    place();
    if (S.tipNode) tipPos();
  }
  function breathe(ctx) {
    var b = ctx && isFin(ctx.breath) ? ctx.breath : 0.5;
    var v = (S.still ? 0.72 : Math.round((0.46 + 0.4 * b) * 50) / 50).toFixed(2);
    if (v === S.breathV) return;
    S.breathV = v;
    for (var i = 0; i < S.nodes.length; i++) if (!S.nodes[i].more) S.nodes[i].el.glow.setAttribute('opacity', v);
  }

  /* ───────────────────────── 悬停联动（M1）/ 点击（M3） ───────────────────────── */
  function nodeOf(key) {
    if (!S || key == null) return null;
    if (key === '+') return S.moreNode;
    for (var i = 0; i < S.nodes.length; i++) if (!S.nodes[i].more && S.nodes[i].name === key) return S.nodes[i];
    return null;
  }
  function linkEls() {
    var g = S.ctx && S.ctx.groups, out = [], i, ch, el;
    [g && g.arcs, g && g.heads].forEach(function (gr) {
      if (!gr) return;
      ch = gr.children;
      for (i = 0; i < ch.length; i++) {
        el = ch[i];
        if (el.classList && (el.classList.contains('cl-ann-arc') || el.classList.contains('cl-ann-head')) && el.getAttribute('data-id') != null) out.push(el);
      }
    });
    if (S.svg) { var labs = S.svg.querySelectorAll('.cl-ann-label[data-id]'); for (i = 0; i < labs.length; i++) out.push(labs[i]); }
    return out;
  }
  function clearLinks() {
    var els = linkEls(), i;
    for (i = 0; i < els.length; i++) { setCls(els[i], 'is-core-on', false); setCls(els[i], 'is-core-off', false); }
    setCls(S.layer, 'core-hover', false);
  }
  function applyHover() {
    var nd = nodeOf(S.hover), star = !!(nd && !nd.more), onIds = {}, els, i, id;
    if (star) nd.lit.forEach(function (x) { onIds[x] = 1; });
    if (star) {
      els = linkEls();
      for (i = 0; i < els.length; i++) {
        id = els[i].getAttribute('data-id');
        setCls(els[i], 'is-core-on', !!onIds[id]); setCls(els[i], 'is-core-off', !onIds[id]);
      }
      setCls(S.layer, 'core-hover', true);
    } else clearLinks();
    setCls(S.g, 'is-hovering', !!nd);
    for (i = 0; i < S.nodes.length; i++) setCls(S.nodes[i].el.g, 'is-hot', S.nodes[i] === nd);
    tipShow(nd);
  }
  function syncHover() {
    if (!S) return;
    var key = S.pointerKey || S.focusKey || S.apiKey || null;
    if (key === S.hover) return;
    S.hover = key; S.hoverChanges++;
    applyHover();
  }
  function tipShow(nd) {
    var T = S.tip;
    if (!nd) { setCls(T.g, 'is-on', false); S.tipNode = null; return; }
    var txt = nd.more ? ('其余 ' + S.more + ' 人 · 点击进入星域') : (nd.name + ' · ' + nd.campName + ' · 参与 ' + nd.lit.length + ' 线');
    if (T.text.textContent !== txt) { T.text.textContent = txt; T.w = 0; }
    if (!T.w) { try { T.w = T.text.getComputedTextLength(); } catch (e) { T.w = 0; } if (!(T.w > 0)) T.w = estW(txt, S.fsTip); }
    S.tipNode = nd; tipPos(); setCls(T.g, 'is-on', true);
  }
  function tipPos() {
    var nd = S.tipNode, T = S.tip;
    if (!nd || !nd.s) return;
    var w = T.w + 14, h = S.fsTip + 10, x = nd.s[0] + nd.rb.r + 8, y = nd.s[1] - h / 2;
    if (x + w > (window.innerWidth || 1440) - 6) x = nd.s[0] - nd.rb.l - 8 - w;
    x = Math.max(4, x); y = clamp(y, 4, (window.innerHeight || 900) - h - 4);
    setA(T.bg, 'x', r1(x)); setA(T.bg, 'y', r1(y)); setA(T.bg, 'width', r1(w)); setA(T.bg, 'height', r1(h));
    setA(T.text, 'x', r1(x + 7)); setA(T.text, 'y', r1(y + h / 2 + S.fsTip * 0.36));
  }
  function starOf(t) {
    while (t && S && t !== S.g) {
      if (t.nodeType === 1 && (t.hasAttribute('data-core-name') || t.hasAttribute('data-core-more'))) return t;
      t = t.parentNode;
    }
    return null;
  }
  function keyOf(el) { return el.hasAttribute('data-core-more') ? '+' : el.getAttribute('data-core-name'); }
  function openGem(name) {
    var P = window.CLAtlasPreview, App = window.CLApp;
    try { if (P && typeof P.active === 'function' && P.active() && typeof P.chooseCharacter === 'function') return !!P.chooseCharacter(name); } catch (e) {}
    try { if (App && App.atlas && typeof App.atlas.view === 'function') return !!App.atlas.view('gem', name); } catch (e2) {}
    return false;
  }
  function openDomains() {
    var P = window.CLAtlasPreview, App = window.CLApp;
    try { if (P && typeof P.active === 'function' && P.active() && typeof P.setAtlas === 'function') return !!P.setAtlas('domains'); } catch (e) {}
    try { if (App && App.atlas && typeof App.atlas.view === 'function') return !!App.atlas.view('domains'); } catch (e2) {}
    return false;
  }
  function activate(el) {
    if (!el) return false;
    return el.hasAttribute('data-core-more') ? openDomains() : openGem(el.getAttribute('data-core-name'));
  }
  function onOver(e) { var el = starOf(e.target); if (!el) return; S.pointerKey = keyOf(el); syncHover(); }
  function onOut(e) {
    var el = starOf(e.target); if (!el) return;
    var to = e.relatedTarget;
    if (to && el.contains(to)) return;
    if (S.pointerKey === keyOf(el)) { S.pointerKey = null; syncHover(); }
  }
  function onFocusIn(e) { var el = starOf(e.target); if (!el) return; S.focusKey = keyOf(el); syncHover(); }
  function onFocusOut() { if (!S) return; S.focusKey = null; syncHover(); }
  function onClick(e) {
    var el = starOf(e.target); if (!el) return;
    /* 不让 annulus-interact 的 document 级「点空处清焦」在同一次点击里把刚选中的人物清掉 */
    e.stopPropagation(); e.preventDefault();
    activate(el);
  }
  /* 键盘：预演会话与 keys.js 在 window 捕获阶段截 Space/Enter；本监听在它们之前注册（脚本序在前），
   * 只在焦点落在星核星上时接管。全局唯一一条，挂载与否都不增殖；未挂载时直接返回。 */
  window.addEventListener('keydown', function (e) {
    if (!S || !S.g) return;
    var k = e.key;
    if (k !== 'Enter' && k !== ' ' && k !== 'Spacebar') return;
    var t = e.target;
    if (!t || t.nodeType !== 1 || !S.g.contains(t)) return;
    var el = starOf(t); if (!el) return;
    e.preventDefault(); e.stopImmediatePropagation();
    activate(el);
  }, true);

  /* ───────────────────────── 插件生命周期 ───────────────────────── */
  function mount(ctx) {
    unmount();
    if (!ctx || !ctx.svg || !ctx.A || !ctx.A.ok) return;
    var G = graph();
    if (!G || !Array.isArray(G.characters)) return;
    var t0 = nowMs();
    live.mounts++;
    S = { ctx: ctx, svg: ctx.svg, layer: ctx.svg.parentNode, A: ctx.A, writes: 0, solves: 0, frames: 0, geoFrames: 0,
      jsMs: 0, jsAvg: 0, jsMax: 0, jsMaxSteady: 0, maxSteadyKind: null, geoCost: [], steady: [], samples: [], bound: [], obst: [], rLab: Infinity, labSig: null, lastC: null, skips: 0, geoApplied: 0, aggEl: null, aggHid: null, aggW: 0, aggH: 0, labVK: null, labDisp: null, styleReads: 0, why: {}, aggKey: null, aggBox: null, sinceSolve: 0, solveRef: null, unsat: false, hover: null, hoverChanges: 0,
      pointerKey: null, focusKey: null, apiKey: null, breathV: null, needSolve: true, dirty: false,
      low: ctx.tier === 'low', fs: tokPx('--cl-ann-core-fs', 10), fsHi: tokPx('--cl-ann-core-fs-hi', 11), fsTip: tokPx('--cl-ann-core-fs-tip', 11) };
    S.still = !!(ctx.reduced || prefersReduced() || S.low);
    buildModel(ctx, G);
    S.H = hom(ctx, S.rIn);
    if (!S.H) { S.H = null; }
    S.aTop = S.H ? Math.round(topAngle() / (Math.PI / 36)) * (Math.PI / 36) : Math.PI / 2;
    if (S.H) buildSeeds(); else { S.aTop = Math.PI / 2; S.H = { m: [1, 0, 0, 0, 1, 0, 0, 0, 1], inv: [1, 0, 0, 0, 1, 0, 0, 0, 1] }; buildSeeds(); S.H = null; }
    buildDom(ctx);
    measureLabels();
    setCls(S.layer, 'core-still', S.still);
    on(S.g, 'pointerover', onOver); on(S.g, 'pointerout', onOut);
    on(S.g, 'focusin', onFocusIn); on(S.g, 'focusout', onFocusOut); on(S.g, 'click', onClick);
    if (document.fonts && typeof document.fonts.addEventListener === 'function') {
      S.onFonts = function () { if (S) { S.remeasure = true; S.dirty = true; } };
      document.fonts.addEventListener('loadingdone', S.onFonts); live.listeners++;
    }
    S.prio = priority();
    S.vp = [window.innerWidth, window.innerHeight];
    geometry();
    S.mountMs = nowMs() - t0;
  }
  function frame(ctx) {
    if (!S || !S.g) return;
    if (ctx && ctx.A && ctx.A !== S.A) return;
    var t0 = nowMs();
    if (ctx) S.ctx = ctx;
    S.frames++;
    var vw = window.innerWidth, vh = window.innerHeight;
    if (vw !== S.vp[0] || vh !== S.vp[1]) {
      S.vp = [vw, vh];
      if (capFor(!!(ctx && ctx.far)) !== S.cap) { mount(ctx || S.ctx); return; }
      S.dirty = true; S.needSolve = true; S.campNamesOff = false;
    }
    if (S.remeasure) { S.remeasure = false; measureLabels(); S.needSolve = true; S.dirty = true; }
    var solves0 = S.solves, skips0 = S.skips, kind = 'idle';
    if ((ctx && ctx.geometryChanged) || S.dirty) { var force = S.dirty; S.dirty = false; S.geoFrames++; geometry(force); kind = S.skips > skips0 ? 'skip' : 'geo'; }
    /* A zero-duration projection redraw must stay entirely quiet.  The SVG
     * owner marks it on the shared frame context so the first core pass does
     * not re-write every glow while geometry is otherwise cached. */
    if (!(ctx && ctx.frozenStep)) breathe(ctx);
    var dt = nowMs() - t0;
    if (S.solves === solves0) {
      S.steady.push(dt); if (S.steady.length > 240) S.steady.shift();
      if (dt > S.jsMaxSteady) { S.jsMaxSteady = dt; S.maxSteadyKind = kind; }
      if (kind === 'geo') { S.geoCost.push(dt); if (S.geoCost.length > 240) S.geoCost.shift(); }
    }
    S.jsMs = dt; S.jsAvg = S.frames > 1 ? S.jsAvg * 0.94 + dt * 0.06 : dt;
    if (dt > S.jsMax) S.jsMax = dt;
    S.samples.push(dt); if (S.samples.length > 240) S.samples.shift();
  }
  function unmount() {
    if (!S) return;
    var st = S, i;
    for (i = 0; i < st.bound.length; i++) { st.bound[i][0].removeEventListener(st.bound[i][1], st.bound[i][2], st.bound[i][3]); live.listeners--; }
    st.bound = [];
    if (st.onFonts && document.fonts && typeof document.fonts.removeEventListener === 'function') { document.fonts.removeEventListener('loadingdone', st.onFonts); live.listeners--; }
    try { clearLinks(); } catch (e) {}
    setCls(st.layer, 'core-hover', false); setCls(st.layer, 'core-still', false);
    if (st.g && st.g.parentNode) st.g.parentNode.removeChild(st.g);
    if (st.tipG && st.tipG.parentNode) st.tipG.parentNode.removeChild(st.tipG);
    S = null;
    live.unmounts++;
  }
  function refresh(ctx) { mount(ctx || (S && S.ctx)); }

  /* ───────────────────────── 探针 ───────────────────────── */
  function pct(arr, p) {
    if (!arr.length) return 0;
    var s = arr.slice().sort(function (a, b) { return a - b; });
    return s[Math.min(s.length - 1, Math.floor((s.length - 1) * p))];
  }
  function stats() {
    if (!S) return { mounted: false, listeners: live.listeners, mounts: live.mounts, unmounts: live.unmounts };
    var maxR = 0, stars = [], i, nd;
    if (S.H && S.pos) {
      for (i = 0; i < S.nodes.length; i++) {
        nd = S.nodes[i];
        var s = toS(S.pos[i][0], S.pos[i][1]), wr = worstR(s, ptsFor(nd, S.mode, S.sides[i]));
        if (wr > maxR) maxR = wr;
        var lb = S.sides[i] ? absB(labelBox(nd, S.mode, S.sides[i]), s) : null;
        stars.push({ name: nd.name, more: !!nd.more, rank: nd.rank, tier: nd.tier, camp: nd.campName, color: nd.color || null,
          x: r2(S.pos[i][0]), y: r2(S.pos[i][1]), r: r2(Math.sqrt(S.pos[i][0] * S.pos[i][0] + S.pos[i][1] * S.pos[i][1])),
          sx: r1(s[0]), sy: r1(s[1]), side: S.sides[i], label: nd.label, labelBox: lb ? lb.map(r1) : null, footprintR: r2(wr),
          rays: nd.rays.map(function (r) { return { i: r.i, key: r.key, score: r.score, L: r2(r.L) }; }),
          unknown: nd.unk.map(function (u) { return u.i; }), lit: nd.lit.slice() });
      }
    }
    return {
      mounted: true, total: S.total, shown: S.shownN, more: S.more, cap: S.cap, far: S.far,
      rIn: r2(S.rIn), rCore: r2(S.rCore), rLab: isFinite(S.rLab) ? r2(S.rLab) : null, limit: r2(S.limit), aTop: r2(S.aTop), mode: S.mode, labelsQuiet: S.fails || 0,
      maxPlaneR: r2(maxR), maxPlaneRatio: S.rIn ? Math.round(maxR / S.rIn * 1000) / 1000 : null,
      solves: S.solves, skips: S.skips, styleReads: S.styleReads, solveWhy: S.why, unsat: !!S.unsat, campNamesOff: !!S.campNamesOff, frames: S.frames, geoFrames: S.geoFrames, writes: S.writes, hover: S.hover, hoverChanges: S.hoverChanges,
      jsMs: Math.round(S.jsMs * 1000) / 1000, jsAvg: Math.round(S.jsAvg * 1000) / 1000, jsMax: Math.round(S.jsMax * 1000) / 1000,
      jsP50: Math.round(pct(S.samples, 0.5) * 1000) / 1000, jsP95: Math.round(pct(S.samples, 0.95) * 1000) / 1000,
      jsMaxSteady: Math.round(S.jsMaxSteady * 1000) / 1000, maxSteadyKind: S.maxSteadyKind,
      geoP50: Math.round(pct(S.geoCost, 0.5) * 1000) / 1000, geoP95: Math.round(pct(S.geoCost, 0.95) * 1000) / 1000, geoN: S.geoCost.length, skips: S.skips, jsP99Steady: Math.round(pct(S.steady, 0.99) * 1000) / 1000,
      mountMs: Math.round((S.mountMs || 0) * 100) / 100,
      dom: (S.g ? S.g.querySelectorAll('*').length + 1 : 0) + (S.tipG ? S.tipG.querySelectorAll('*').length + 1 : 0),
      camps: (S.campSeq || []).map(function (cp) { return { name: cp.name, color: cp.color, n: cp.members.length, a0: r2(cp.a0), a1: r2(cp.a1), text: cp.shownText }; }),
      world: S.world.map(function (w) { return { key: w.key, n: w.n, partial: w.partial }; }),
      aggregateBox: S.aggBox ? S.aggBox.map(r1) : null, counts: S.counts, badgeText: S.badge.halves.map(function (h) { return h.shown; }),
      listeners: live.listeners, mounts: live.mounts, unmounts: live.unmounts, still: S.still, low: S.low,
      stars: stars
    };
  }
  function hover(name) {
    if (!S) return false;
    S.apiKey = name == null ? null : (name === '+' ? '+' : String(name));
    syncHover();
    return S.hover;
  }
  function relayout() {
    if (!S) return null;
    S.needSolve = true; geometry();
    return S.pos ? S.pos.map(function (p) { return [r2(p[0]), r2(p[1])]; }) : null;
  }

  var plugin = { name: 'core', mount: mount, frame: frame, refresh: refresh, unmount: unmount, stats: stats };
  window.CLAnnulusCore = {
    name: 'annulus-core', version: 'v90', plugin: plugin, stats: stats, hover: hover, relayout: relayout,
    participation: function (name) { var nd = nodeOf(name); return nd ? nd.lit.slice() : null; },
    debug: function () {
      if (!S || !S.H) return null;
      var ell = [], i;
      for (i = 0; i < 16; i++) { var q = polar(S.limit, i * Math.PI / 8); ell.push([r1(q[0]), r1(q[1])]); }
      return { trace: S.trace, rLab: S.rLab, campOff: !!S.campNamesOff, cS: S.cS.map(r1), limitEllipse: ell, obst: S.obst.map(function (o) { return o.map(r1); }),
        nodes: S.nodes.map(function (nd) { return { name: nd.name, lw: r1(nd.lw), lh: r1(nd.lh), rb: nd.rb, cr: nd.cr, gr: nd.gr, seedS: toS(nd.seed[0], nd.seed[1]).map(r1) }; }) };
    },
    activate: function (name) { return name === '+' ? openDomains() : openGem(name); }
  };
  if (window.CLAnnulusSVG && typeof window.CLAnnulusSVG.use === 'function') window.CLAnnulusSVG.use(plugin);
})();
