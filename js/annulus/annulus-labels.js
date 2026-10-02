/**
 * @role component
 * @owns js/annulus/annulus-labels.js
 * @budget dom≤110; frame≤1.2ms
 * @contract v80
 */
/* 沿弧线名·更替标签·章节刻度；自注册 use()；reduce/tier low 时刻度只留章号；无动画；零 inline style */
/* v90 F2 出画治理：任何沿弧/更替标签的包围盒必须完全落在「安全视口」内——视口扣除顶部 HUD 带与
 * 底部时间轴带（safeBand 现读 #atlasPreviewHUD 各行矩形），并避让收起态章回竖签（CLOrbit3DRuler.dockRect）。
 * 出画时：更替标签先沿弧反向展开（锚点翻面）、径向外推，再翻到主线带内侧；沿弧线名沿弧滑动到画内的一段
 * （子路径居中，正立方向按落点切线重判）。仍放不下 → 按既有规则折进账本（is-hidden）并在弧端/更替点留「…」标。
 * 不缩字号。选中/悬停的线名例外：放不进也保留可读（用户明确要看它）。 */
/* v90 P1 帧耗：移动帧（镜头漂移/旋转 → geometryRevision 变）不再读 DOM 几何——
 *  ① 安全区缓存：HUD/竖签矩形只在 safeKey 变、HUD 子树/竖签/body·html 相关属性变（MutationObserver，逐帧 takeRecords 同帧生效）、
 *     尺寸变（ResizeObserver 兜底）、字体变时重读；
 *  ② 沿弧线名包围盒走解析几何：每个标签只在挂载/字体/视口变时用横排克隆量一次逐字起点与字格（getStartPositionOfChar/getExtentOfChar），
 *     之后按 SVG2 textPath 放字规则（startOffset 50% + middle：字中点弧长 = L/2 − W/2 + x_i + a_i/2，字格绕切线旋转）求旋转字格 AABB 并集；
 *     首次量度同帧与真 getBoundingClientRect 对账，超 0.25px 的标签永久回退真读；有字落出路径（Chrome 会藏字）时本帧回退真读；
 *  ③ 显隐（手机支线名 display:none）按「视口 + body/html 类 + is-active」缓存一次 computed display；
 *  ④ 先算完再批量写：可见性 V() 延到决定之后一次写；刻度/章号/更替标签值不变不写。
 * 布局规则、候选序、阈值与改前逐项一致（tests/annulus_labels_perf_v90.py 冻结姿态逐标签对照）。 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var S = { reg: 0, mounted: 0, labels: 0, handoffs: 0, ticks: 0, nums: 0, hidden: 0, lh: 0, layoutPasses: 0, frozenFrames: 0, rectReads: 0,
    slid: 0, flipped: 0, folded: 0, more: 0,
    analytic: 0, fallback: 0, metricPasses: 0, mismatch: 0, safeReads: 0, styleReads: 0 };
  var R = {
    A: null, v: null, g: null, rings: [], arcs: {}, H: [], T: [], N: [], LP: [], M: [],
    fsL: 10, fsH: 10, fsC: 9, gap: 6, notch: 7, tk: 5, co: 22,
    cx: 0, cy: 0, low: 0, k: 1, ts: 1, far: 0, projectXY: null, layoutKey: null, fontRevision: 0, metricRevision: null,
    safe: null
  };
  var EDGE = 2;   /* 安全视口内缩 px */
  /* v90：HUD 带 / 时间轴带之间的安全带（视口坐标）。HUD 未开 = 整个视口。 */
  function safeBand() {
    var W = window.innerWidth || 1200, H = window.innerHeight || 800, top = 0, bottom = H;
    var hud = document.getElementById('atlasPreviewHUD');
    if (hud && hud.classList.contains('on')) {
      var kids = hud.querySelectorAll('.aph-shell > *'), i, r;
      for (i = 0; i < kids.length; i++) {
        r = kids[i].getBoundingClientRect();
        if (!(r.height > 0) || !(r.width > 0)) continue;
        if (r.bottom <= H * 0.5) { if (r.bottom > top) top = r.bottom; }
        else if (r.top >= H * 0.5) { if (r.top < bottom) bottom = r.top; }
      }
    }
    return { left: 0, top: top, right: W, bottom: bottom };
  }
  function safeKey() {
    var hud = document.getElementById('atlasPreviewHUD'), dk = '';
    try { if (window.CLOrbit3DRuler && CLOrbit3DRuler.dockKey) dk = CLOrbit3DRuler.dockKey(); } catch (e) {}
    return (window.innerWidth || 0) + 'x' + (window.innerHeight || 0) + (hud && hud.classList.contains('on') ? 'h' : '') + dk;
  }
  /* 安全区 = 安全带内缩 EDGE + 障碍（收起态竖签） */
  function safeArea() {
    var b = safeBand(), obs = [], d = null;
    try { d = window.CLOrbit3DRuler && CLOrbit3DRuler.dockRect ? CLOrbit3DRuler.dockRect() : null; } catch (e) { d = null; }
    if (d && !d.open) obs.push([d.left - 4, d.top - 4, d.right + 4, d.bottom + 4]);
    return { r: [b.left + EDGE, b.top + EDGE, b.right - EDGE, b.bottom - EDGE], obs: obs };
  }
  function fits(rc) {
    var s = R.safe, i;
    if (!s) return true;
    if (rc[0] < s.r[0] || rc[1] < s.r[1] || rc[2] > s.r[2] || rc[3] > s.r[3]) return false;
    for (i = 0; i < s.obs.length; i++) if (inter(rc, s.obs[i])) return false;
    return true;
  }
  /* v90 P1 安全区缓存：值与每帧重读完全相同，只是不在「别的插件刚写完 SVG」的移动帧里强制布局。
   * 失效源：safeKey（视口/HUD 开关/竖签态）· HUD 子树任意变更 · 竖签根属性 · body/html 与版式相关的属性 · 尺寸（RO 兜底）· 字体。 */
  var SAFE = { val: null, key: null, dirty: true, mo: null, ro: null, hud: null, dock: null, seen: null, anims: [], evs: [] };
  var BODY_ATTRS = ['class', 'style', 'hidden', 'data-atlas-view', 'data-atlas-lens'];
  /* 位移类动画（竖签根 transform 过渡、面板滑入等）既不是 DOM 变更也不改尺寸：MO/RO 都看不见——
   * 所以 HUD/竖签子树上「会动几何」的过渡/动画在跑时，每次排布照旧重读（与改前逐帧真读等价），停了再读一次终值。
   * 纯视觉属性（透明度/颜色/阴影/滤镜…）的动画不影响矩形，忽略。 */
  var NONGEO = /^(opacity|color|background(-[a-z-]+)?|box-shadow|filter|-webkit-backdrop-filter|backdrop-filter|border(-top|-right|-bottom|-left)?-color|outline(-[a-z-]+)?|text-shadow|fill(-opacity)?|stroke(-[a-z-]+)?|visibility|caret-color|text-decoration(-[a-z-]+)?|cursor)$/;
  var ANIM_EVS = ['transitionrun', 'transitionstart', 'animationstart'];
  function geoAnim(a) {
    try {
      if (a.transitionProperty) return !NONGEO.test(String(a.transitionProperty));
      var kf = a.effect && a.effect.getKeyframes ? a.effect.getKeyframes() : null, i, k;
      if (!kf || !kf.length) return true;
      for (i = 0; i < kf.length; i++) for (k in kf[i]) {
        if (k === 'offset' || k === 'computedOffset' || k === 'easing' || k === 'composite') continue;
        if (!NONGEO.test(k.replace(/[A-Z]/g, function (m) { return '-' + m.toLowerCase(); }))) return true;
      }
      return false;
    } catch (e) { return true; }
  }
  function trackAnims(el, sub) {
    if (!el || typeof el.getAnimations !== 'function') return;
    var list = [], i;
    try { list = sub ? el.getAnimations({ subtree: true }) : el.getAnimations(); } catch (e) { list = []; }
    for (i = 0; i < list.length; i++) {
      var ps = list[i].playState;
      if (ps === 'finished' || ps === 'idle' || SAFE.anims.indexOf(list[i]) >= 0 || !geoAnim(list[i])) continue;
      SAFE.anims.push(list[i]); SAFE.dirty = true;
    }
  }
  function onAnim(e) { trackAnims(e && e.target, false); }
  /* 每次排布：有位移动画在跑 → 重读；刚结束/被取消 → 再读一次终值后移出 */
  function animPoll() {
    if (!SAFE.anims.length) return;
    var live = [], i, ps;
    for (i = 0; i < SAFE.anims.length; i++) {
      try { ps = SAFE.anims[i].playState; } catch (e) { ps = 'idle'; }
      if (ps === 'finished' || ps === 'idle') { SAFE.dirty = true; continue; }
      if (ps === 'running') SAFE.dirty = true;
      live.push(SAFE.anims[i]);
    }
    SAFE.anims = live;
  }
  function safeUnbind() {
    try { if (SAFE.mo) SAFE.mo.disconnect(); } catch (e) {}
    try { if (SAFE.ro) SAFE.ro.disconnect(); } catch (e2) {}
    for (var i = 0; i < SAFE.evs.length; i++) { try { SAFE.evs[i][0].removeEventListener(SAFE.evs[i][1], onAnim, true); } catch (e3) {} }
    SAFE.mo = null; SAFE.ro = null; SAFE.hud = null; SAFE.dock = null; SAFE.seen = null; SAFE.val = null; SAFE.key = null; SAFE.dirty = true;
    SAFE.anims = []; SAFE.evs = [];
  }
  function safeDirty() { SAFE.dirty = true; }
  function safeBind(hud, dock) {
    safeUnbind();
    SAFE.hud = hud; SAFE.dock = dock;
    var els = [hud, dock], i, j;
    for (i = 0; i < els.length; i++) if (els[i]) for (j = 0; j < ANIM_EVS.length; j++) { els[i].addEventListener(ANIM_EVS[j], onAnim, true); SAFE.evs.push([els[i], ANIM_EVS[j]]); }
    trackAnims(hud, true); trackAnims(dock, true);   /* 绑定前就已在跑的（进工作区那一刻的竖签滑入） */
    if (typeof MutationObserver !== 'function') return;
    try {
      SAFE.mo = new MutationObserver(safeDirty);
      if (hud) SAFE.mo.observe(hud, { attributes: true, childList: true, characterData: true, subtree: true });
      if (dock) SAFE.mo.observe(dock, { attributes: true });
      if (document.body) SAFE.mo.observe(document.body, { attributes: true, attributeFilter: BODY_ATTRS });
      SAFE.mo.observe(document.documentElement, { attributes: true, attributeFilter: BODY_ATTRS });
      if (typeof ResizeObserver === 'function') {
        SAFE.ro = new ResizeObserver(safeDirty); SAFE.seen = typeof WeakSet === 'function' ? new WeakSet() : null;
        if (hud) SAFE.ro.observe(hud);
        if (dock) SAFE.ro.observe(dock);
      }
    } catch (e) { safeUnbind(); }
  }
  /* RO 只挂一次/元素：重复 observe 会触发初始回调 → 永远 dirty */
  function safeWatchKids(hud) {
    if (!SAFE.ro || !SAFE.seen || !hud) return;
    var kids = hud.querySelectorAll('.aph-shell > *'), i;
    for (i = 0; i < kids.length; i++) if (!SAFE.seen.has(kids[i])) { SAFE.seen.add(kids[i]); try { SAFE.ro.observe(kids[i]); } catch (e) {} }
  }
  function safeCached() {
    var hud = document.getElementById('atlasPreviewHUD'), dock = null, key = safeKey();
    try { dock = document.querySelector('.cl-o3-ruler'); } catch (e) { dock = null; }
    if (hud !== SAFE.hud || dock !== SAFE.dock) safeBind(hud, dock);
    if (!SAFE.mo) SAFE.dirty = true;
    else if (SAFE.mo.takeRecords().length) SAFE.dirty = true;   /* 本任务内刚发生、尚未投递的变更也算：同帧生效 */
    animPoll();
    if (!SAFE.dirty && SAFE.val && SAFE.key === key) return SAFE.val;
    SAFE.val = safeArea(); SAFE.key = key; SAFE.dirty = false; S.safeReads++;
    safeWatchKids(hud);
    return SAFE.val;
  }
  function mk(t, c) { var e = document.createElementNS(NS, t); if (c) e.setAttribute('class', c); return e; }
  function cn(n, fb) {
    try {
      var v = (getComputedStyle(document.documentElement).getPropertyValue(n) || '').trim();
      var f = parseFloat(v);
      if (isFinite(f) && f > 0) return f;
    } catch (e) {}
    return fb;
  }
  function AC(e, c) { if (e.classList) e.classList.add(c); }
  function RC(e, c) { if (e.classList) e.classList.remove(c); }
  function V(e, on) {
    if (e.__clAnnLabelVisible === !!on) return;
    e.__clAnnLabelVisible = !!on;
    if (on) { RC(e, 'hidden'); RC(e, 'is-hidden'); e.removeAttribute('opacity'); e.removeAttribute('hidden'); }
    else { AC(e, 'hidden'); AC(e, 'is-hidden'); e.setAttribute('opacity', '0'); e.setAttribute('hidden', ''); }
  }
  function st() { try { return CLOrbit3DLayer.stats() || null; } catch (e) { return null; } }
  /* P1：low()/red() 同帧共用一次 CLOrbit3DLayer.stats()（原来各调一次）；减动效 MediaQueryList 建一次（.matches 是实时的） */
  var RMQ = null, stMemo = null;
  function stOnce() { if (stMemo === null) stMemo = st() || 0; return stMemo || null; }
  function low() {
    try { if (CLOrbit3DTier && CLOrbit3DTier.get() === 'low') return 1; } catch (e) {}
    var s = stOnce();
    if (s && s.tier === 'low') return 1;
    return navigator.hardwareConcurrency <= 4 ? 1 : 0;
  }
  function red() {
    try { if (!RMQ) RMQ = matchMedia('(prefers-reduced-motion: reduce)'); if (RMQ.matches) return 1; } catch (e) {}
    var s = stOnce();
    return s && s.reduced ? 1 : 0;
  }
  function envLow() { stMemo = null; var v = low() || red(); stMemo = null; return v; }
  /* P1：「x y」段的快速解析——与 seg.trim().split(/[ ,]+/) 取前两数逐值相同；非此格式走原正则 */
  function segXY(sg) {
    var sp = sg.indexOf(' ');
    if (sp > 0 && sg.indexOf(' ', sp + 1) < 0 && sg.indexOf(',') < 0 && sg.charCodeAt(0) > 32) return [+sg.slice(0, sp), +sg.slice(sp + 1)];
    var xy = sg.trim().split(/[ ,]+/);
    return [+xy[0], +xy[1]];
  }
  function L(x, y) {
    try { var p = CLOrbit3DLayer.localToGroup(x, y, 0); if (p && p.length > 1) return p; } catch (e) {}
    return [x, y];
  }
  function SC(p) {
    try { if (R.v && R.v.screenOf) { var s = R.v.screenOf(p); return s || null; } } catch (e) {}
    return [p[0], p[1]];
  }
  function PX(x, y) { return R.projectXY ? R.projectXY(x, y) : SC(L(x, y)); }
  function n2(v) { return Math.round(v * 100) / 100; }
  function estW(s, fs) {
    var w = 0, i;
    for (i = 0; i < s.length; i++) w += s.charCodeAt(i) > 0x2e7f ? fs : fs * 0.55;
    return w;
  }
  function inter(a, b) { return !(a[2] <= b[0] || b[2] <= a[0] || a[3] <= b[1] || b[3] <= a[1]); }
  function pickA(c) { return (c && c.A) || R.A; }
  function ringById(id) {
    var i;
    for (i = 0; i < R.rings.length; i++) if (String(R.rings[i].id) === String(id)) return R.rings[i];
    return null;
  }
  function nameOf(id) {
    var r = ringById(id);
    if (!r) return id ? String(id) : '';
    return String(r.shortName || r.name || id || '');
  }
  var lengthSamples = new WeakMap();
  function arcLen(rg) {
    var K = 48, prev = null, len = 0, hits = 0, i, a, s;
    var cached = lengthSamples.get(rg), key = [rg.r, rg.a0, rg.a1].join('|');
    if (!cached || cached.key !== key) {
      cached = { key: key, points: [] };
      for (i = 0; i <= K; i++) { a = rg.a0 + (rg.a1 - rg.a0) * (i / K); cached.points.push([rg.r * Math.cos(a), rg.r * Math.sin(a)]); }
      lengthSamples.set(rg, cached);
    }
    for (i = 0; i <= K; i++) {
      s = PX(cached.points[i][0], cached.points[i][1]);
      if (!s) { prev = null; continue; }
      hits++;
      if (prev) { var dx = s[0] - prev[0], dy = s[1] - prev[1]; len += Math.sqrt(dx * dx + dy * dy); }
      prev = s;
    }
    return hits >= 2 ? len : 0;
  }
  function arcEl(rg) {
    var e = R.arcs[rg.id] || null;
    if (!e) {
      e = document.querySelector('.cl-ann-arc[data-id="' + String(rg.id).replace(/"/g, '\\"') + '"]');
    }
    if (e) { if (!e.id) e.id = 'cl-ann-arc-' + rg.id; R.arcs[rg.id] = e; }
    return e;
  }
  function buildLabel(rg) {
    if (!rg || !rg.valid || !(rg.eventCount >= 1) || !isFinite(rg.r) || !rg.shortName) return;
    var arc = arcEl(rg);
    if (!arc) return;
    var lp = mk('path', 'cl-ann-label-path');
    lp.setAttribute('id', 'cl-ann-lp-' + String(rg.id));
    lp.setAttribute('fill', 'none');
    R.g.appendChild(lp);
    var t = mk('text', 'cl-ann-label'), tp = mk('textPath'), frag = '#cl-ann-lp-' + String(rg.id);
    t.setAttribute('data-kind', rg.kind || 'branch'); t.setAttribute('data-id', String(rg.id));
    tp.setAttribute('href', frag);
    tp.setAttribute('startOffset', '50%');
    t.setAttribute('text-anchor', 'middle');
    R.LP.push({ arc: arc, lp: lp, t: t, rg: rg, short: false, active: false, anchor: null, lastAnchor: '' });
    tp.appendChild(document.createTextNode(String(rg.shortName)));
    t.appendChild(tp);
    R.g.appendChild(t);
    S.labels++;
    var len = arcLen(rg);
    if (!(len > 0) || len < estW(String(rg.shortName), R.fsL) + 2 * R.gap) { V(t, false); S.lh++; R.LP[R.LP.length - 1].short = true; }
  }
  function buildHandoffs(A) {
    var hs = (A.handoffs || []).slice(0), i;
    hs.sort(function (p, q) { return (p.gen || 0) - (q.gen || 0); });
    for (i = 0; i < hs.length && R.H.length < 8; i++) {
      var h = hs[i];
      if (!isFinite(h.a)) continue;
      var na = nameOf(h.fromId), nb = nameOf(h.toId);
      if (!na || !nb) continue;
      var txt = na + ' \u2192 ' + nb;
      var t = mk('text', 'cl-ann-handoff-label');
      t.appendChild(document.createTextNode(txt));
      R.g.appendChild(t);
      var rg = ringById(h.fromId) || ringById(h.toId);
      R.H.push({ el: t, a: h.a, r: (rg && isFinite(rg.r)) ? rg.r : (A.R || 0), txt: txt });
      S.handoffs++;
    }
  }
  function buildChapters(A) {
    var ch = A.chapters || [], n = ch.length, i;
    R.k = Math.max(1, Math.ceil(n / 12));
    R.ts = Math.max(1, Math.ceil(n / 60));
    if (!R.low && !R.far) {   /* far：章界细刻不画，只留章号 */
      for (i = 0; i < n; i += R.ts) {
        if (!isFinite(ch[i].a0)) continue;
        var p = mk('path', 'cl-ann-chapter-tick');
        R.g.appendChild(p);
        R.T.push({ el: p, a: ch[i].a0 });
        S.ticks++;
      }
    }
    for (i = 0; i < n; i += R.k) {
      if (!isFinite(ch[i].a0)) continue;
      var t = mk('text', 'cl-ann-chapter-num');
      t.appendChild(document.createTextNode(String((ch[i].idx != null ? ch[i].idx : i) + 1)));
      R.g.appendChild(t);
      R.N.push({ el: t, a: ch[i].a0 });
      S.nums++;
    }
  }
  function findHost(c) {
    var first = document.querySelector('.cl-ann-arc');
    if (first) return first.parentNode;
    if (c) {
      var h = c.g || c.root;
      if (h && h.appendChild) return h;
    }
  }
  function mount(c) {
    unmount();
    var A = pickA(c);
    if (!A || !A.ok || !A.rings || !A.rings.length) return;
    R.A = A;
    R.v = (c && c.view) || R.v;
    R.projectXY = c && c.projectXY || null;
    R.low = envLow();
    R.fsL = cn('--cl-ann-fs-label', 10);
    R.fsH = cn('--cl-ann-fs-handoff', 9);
    R.fsC = cn('--cl-ann-fs-chapter', 9);
    R.gap = cn('--cl-ann-label-gap', 6);
    R.notch = cn('--cl-ann-notch', 7);
    R.tk = cn('--cl-ann-tick-len', 5);
    R.co = cn('--cl-ann-chapter-r-off', 22);
    var host = findHost(c);
    if (!host) return;
    var arcs = document.querySelectorAll('.cl-ann-arc'), i, aid;
    R.arcs = {};
    for (i = 0; i < arcs.length; i++) {
      aid = arcs[i].getAttribute('data-id') || '';
      if (aid) R.arcs[aid] = arcs[i];
      if (aid && !arcs[i].id) arcs[i].id = 'cl-ann-arc-' + aid;
    }
    R.rings = A.rings;
    var c0 = PX(0, 0) || L(0, 0);   /* 主控：盘心取屏幕坐标，后续左右半盘判定才有意义 */
    R.cx = c0[0]; R.cy = c0[1];
    R.g = mk('g', 'cl-ann-labels');
    host.appendChild(R.g);
    /* 主控：far LOD 下支线只给前 8 长的线沿弧标签，其余名字留在账本 */
    var far = !!(c && c.far), allow = {};
    R.far = far;
    if (far) {
      var br = [], bi;
      for (bi = 0; bi < A.rings.length; bi++) if (A.rings[bi].kind !== 'main') br.push(A.rings[bi]);
      br.sort(function (x, y) { return (y.eventCount || 0) - (x.eventCount || 0); });
      for (bi = 0; bi < br.length && bi < 8; bi++) allow[String(br[bi].id)] = 1;
    }
    for (i = 0; i < A.rings.length; i++) if (!far || A.rings[i].kind === 'main' || allow[String(A.rings[i].id)]) buildLabel(A.rings[i]);
    buildHandoffs(A);
    buildChapters(A);
    S.mounted = 1;
    if (document.fonts && document.fonts.addEventListener) document.fonts.addEventListener('loadingdone', fontsChanged);
    frame(c);
  }
  function fontsChanged() {
    R.fontRevision++; R.layoutKey = null;
    for (var i = 0; i < R.H.length; i++) { R.H[i].bw = 0; R.H[i].bh = 0; }
    SAFE.dirty = true;   /* HUD 行高也可能随字体变 */
  }
  /* ───── v90 P1：沿弧线名解析包围盒 ───── */
  var EMPTY = [0, 0, 0, 0];           /* 「宽 0」哨兵：display:none / 空路径——与真读 width 0 同样跳过 */
  var PATH_EPS = 0.05, CHECK_TOL = 0.25, LENS = [];
  function metricKey() { return R.fontRevision + '|' + (window.innerWidth || 0) + 'x' + (window.innerHeight || 0); }
  function dispBase() {
    var b = document.body, h = document.documentElement;
    return (window.innerWidth || 0) + 'x' + (window.innerHeight || 0) + '|' + (b ? String(b.className) + '|' + (b.getAttribute('data-atlas-view') || '') : '') + '|' + (h ? String(h.className) : '');
  }
  /* 真读时 width>0 的前提：自身到 body 的祖先链都不是 display:none（手机支线名规则、工作区隐藏规则都走这里） */
  function shown(el) {
    var n = el;
    try {
      while (n && n.nodeType === 1 && n !== document.body) { if (getComputedStyle(n).display === 'none') return false; n = n.parentNode; }
    } catch (e) { return true; }
    return !!(n);
  }
  /* 横排克隆一次量完：逐字起点 x_i、字格宽 a_i、字格上下沿（相对基线）；与沿路径排版同一字体/字距/整形 */
  function measure(items, mkey) {
    var cl = [], i, k, it, c, ctm = null;
    for (i = 0; i < items.length; i++) {
      it = items[i];
      c = mk('text', String(it.t.getAttribute('class') || '').replace(/(^|\s)(?:is-hidden|hidden)(?=\s|$)/g, '$1').replace(/\s+/g, ' ').trim());
      c.setAttribute('data-kind', it.t.getAttribute('data-kind') || '');
      c.appendChild(document.createTextNode(String(it.rg.shortName)));
      R.g.appendChild(c); cl.push(c);
    }
    try { ctm = R.g.getScreenCTM(); } catch (e0) { ctm = null; }
    var plain = !!ctm && Math.abs(ctm.a - 1) < 1e-9 && Math.abs(ctm.d - 1) < 1e-9 && Math.abs(ctm.b) < 1e-9 && Math.abs(ctm.c) < 1e-9;
    for (i = 0; i < items.length; i++) {
      var met = { key: mkey, ok: false, checked: false, n: 0, x: [], a: [], t: [], b: [], x0: 0, W: 0, ox: 0, oy: 0 };
      try {
        var n = plain ? cl[i].getNumberOfChars() : 0, ok = n > 0, prev = -Infinity;
        for (k = 0; k < n && ok; k++) {
          var sp = cl[i].getStartPositionOfChar(k), ex = cl[i].getExtentOfChar(k);
          if (!isFinite(sp.x) || !(ex.width > 0) || !(ex.height > 0) || sp.x < prev - 0.5) ok = false;
          prev = sp.x;
          met.x.push(sp.x); met.a.push(ex.width); met.t.push(ex.y); met.b.push(ex.y + ex.height);
        }
        if (ok) {
          met.n = n; met.x0 = met.x[0]; met.W = met.x[n - 1] + met.a[n - 1] - met.x0;
          met.ox = ctm.e; met.oy = ctm.f; met.ok = met.W > 0;
        }
      } catch (e1) { met.ok = false; }
      items[i].met = met;
    }
    for (i = 0; i < cl.length; i++) if (cl[i].parentNode) cl[i].parentNode.removeChild(cl[i]);
    S.metricPasses++;
  }
  /* SVG2 textPath（startOffset 50% + text-anchor middle）：字中点弧长 mid_i = L/2 − W/2 + (x_i − x_0) + a_i/2；
   * 字格 [−a/2, a/2]×[top, bottom] 以该点为心、绕所在折线段切线旋转；返回全部字格旋转 AABB 的并集（视口坐标）。
   * 有字中点落到路径两端外（Chrome 会藏字）→ null，调用方回退真读。 */
  function textRect(pts, met) {
    var n = pts ? pts.length : 0, i, L = 0, dx, dy;
    if (n < 2) return null;
    LENS[0] = 0;
    for (i = 1; i < n; i++) { dx = pts[i][0] - pts[i - 1][0]; dy = pts[i][1] - pts[i - 1][1]; L += Math.sqrt(dx * dx + dy * dy); LENS[i] = L; }
    var off = L / 2 - met.W / 2 - met.x0, seg = 1, x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, k;
    for (k = 0; k < met.n; k++) {
      var a = met.a[k], mid = off + met.x[k] + a / 2;
      if (!(mid > PATH_EPS) || !(mid < L - PATH_EPS)) return null;
      while (seg < n - 1 && LENS[seg] < mid) seg++;
      var p0 = pts[seg - 1], p1 = pts[seg], dl = LENS[seg] - LENS[seg - 1];
      if (!(dl > 1e-9)) return null;
      var cs = (p1[0] - p0[0]) / dl, sn = (p1[1] - p0[1]) / dl, u = (mid - LENS[seg - 1]) / dl;
      var px = p0[0] + (p1[0] - p0[0]) * u, py = p0[1] + (p1[1] - p0[1]) * u, hx = a / 2, tp = met.t[k], bt = met.b[k];
      var ax = hx * cs, ay = hx * sn, tx = -tp * sn, ty = tp * cs, bx = -bt * sn, by = bt * cs, X, Y;
      X = px - ax + tx; Y = py - ay + ty; if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
      X = px + ax + tx; Y = py + ay + ty; if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
      X = px + ax + bx; Y = py + ay + by; if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
      X = px - ax + bx; Y = py - ay + by; if (X < x0) x0 = X; if (X > x1) x1 = X; if (Y < y0) y0 = Y; if (Y > y1) y1 = Y;
    }
    return [x0 + met.ox, y0 + met.oy, x1 + met.ox, y1 + met.oy];
  }
  function rectDiff(a, b) { return Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]), Math.abs(a[2] - b[2]), Math.abs(a[3] - b[3])); }
  function domRect(t) {
    var br = t.getBoundingClientRect(); S.rectReads++;
    return br.width > 0 ? [br.left, br.top, br.right, br.bottom] : EMPTY;
  }
  function metOf(item) { var m = item.met; return m && m.ok && m.checked && m.key === R.mkey ? m : null; }
  function setIf(el, k, v, memo) { if (el[memo] !== v) { el[memo] = v; el.setAttribute(k, v); } }
  function anchorPath(item, d) {
    if (d && !item.anchor) { item.anchor = mk('path', 'cl-ann-label-tether'); R.g.appendChild(item.anchor); }
    if (item.anchor && item.lastAnchor !== d) { item.anchor.setAttribute('d', d); item.lastAnchor = d; }
  }
  function shortLabel(item) {
    var ring = item.rg, a = (ring.a0 + ring.a1) / 2;
    var p = PX(ring.r * Math.cos(a), ring.r * Math.sin(a));
    if (!p) return '';
    var width = estW(String(ring.shortName), R.fsL) + R.gap * 2;
    var x = Math.max(width / 2 + 10, Math.min((window.innerWidth || 1440) - width / 2 - 10, p[0]));
    var y = p[1] - R.fsL - R.gap;
    anchorPath(item, 'M' + n2(p[0]) + ' ' + n2(p[1]) + 'L' + n2(x) + ' ' + n2(y + 3));
    return 'M' + n2(x - width / 2) + ' ' + n2(y) + 'L' + n2(x + width / 2) + ' ' + n2(y);
  }
  function frame(c) {
    if (!S.mounted || !R.g) return;
    if (c && c.view) R.v = c.view;
    if (c && c.projectXY) R.projectXY = c.projectXY;
    R.A = pickA(c) || R.A;
    R.low = envLow();
    var nextKey = c && typeof c.geometryRevision === 'number' ?
      JSON.stringify([c.geometryRevision, c.hover, c.focus, R.low, R.fontRevision, safeKey()]) : null;
    if (nextKey !== null && nextKey === R.layoutKey) { S.frozenFrames++; return; }
    R.layoutKey = nextKey; S.layoutPasses++;
    /* v90：本次排布的安全视口（先读后写：放在任何 SVG 写入之前，避免额外强制布局） */
    R.safe = safeCached(); R.mUsed = 0;
    if (c && c.geometryRevision !== R.metricRevision) {
      // 同一判据随实际投影重新核对：启动时未就绪或缩放后不能把旧的“短弧”
      // 结论永久缓存。阈值、采样数和标签优先级均保持原契约。
      R.metricRevision = c.geometryRevision; S.lh = 0;
      for (var ri = 0; ri < R.LP.length; ri++) {
        var item = R.LP[ri], length = arcLen(item.rg);
        item.short = !(length > 0) || length < estW(String(item.rg.shortName), R.fsL) + 2 * R.gap;
        if (item.short) { V(item.t, false); S.lh++; }
      }
    }
    var i, j, o, hid = S.lh, seen = [];
    /* Reverse by the tangent where the label actually sits (half screen length).
     * The chord between endpoints points the wrong way on near-full circles. */
    for (i = 0; i < R.LP.length; i++) {
      var labelItem = R.LP[i];
      labelItem.active = !!(c && ((c.focus != null && String(c.focus) === String(labelItem.rg.id)) ||
        (c.hover != null && String(c.hover) === String(labelItem.rg.id))));
      /* v90：选中/悬停的线名带 is-active——手机「支线名折进账本」的 CSS 对它让路，被选中的支线名始终可读 */
      if (labelItem.isActiveCls !== labelItem.active) { labelItem.isActiveCls = labelItem.active; if (labelItem.active) AC(labelItem.t, 'is-active'); else RC(labelItem.t, 'is-active'); }
      if (labelItem.short && !labelItem.active) { V(labelItem.t, false); anchorPath(labelItem, ''); continue; }
      /* A chosen short arc still needs a readable name. Keep the actual 3D
       * anchor and use one local callout, never a second text-only screen. */
      var dArc = labelItem.short ? shortLabel(labelItem) : (labelItem.arc.getAttribute('d') || '');
      if (labelItem.short) hid--; else anchorPath(labelItem, '');
      /* P1：labelItem.pts 始终 = DOM 中 label-path 的折线（只在真写 d 时更新），解析包围盒据此放字 */
      if (dArc.length < 4) { R.LP[i].lp.setAttribute('d', ''); labelItem.pts = null; continue; }
      var segs = dArc.replace(/^M/, '').split('L'), coords = [], lens = [], total = 0, si;
      for (si = 0; si < segs.length; si++) {
        coords.push(segXY(segs[si]));
        if (si) { var dxs = coords[si][0] - coords[si - 1][0], dys = coords[si][1] - coords[si - 1][1]; total += Math.sqrt(dxs * dxs + dys * dys); }
        lens.push(total);
      }
      var middle = 1, flipped = false;
      while (middle < lens.length - 1 && lens[middle] < total / 2) middle++;
      if (coords[middle] && coords[middle - 1] && coords[middle][0] < coords[middle - 1][0]) { segs.reverse(); dArc = 'M' + segs.join('L'); flipped = true; }
      if (R.LP[i].lastPath !== dArc) {
        R.LP[i].lp.setAttribute('d', dArc); R.LP[i].lastPath = dArc;
        labelItem.pts = flipped ? coords.reverse() : coords;
      }
    }
    /* W1.5/W5：更替标签落位——真实旋转包围盒 + 领衔珠障碍 + 径向外推 ≤4 步，仍挤不下才隐藏 */
    var beads = document.querySelectorAll('.cl-ann-bead:not(.is-quiet)'), bi, bm, bc;
    for (bi = 0; bi < beads.length; bi++) {
      bm = /translate\(\s*([-\d.]+)[ ,]+([-\d.]+)/.exec(beads[bi].getAttribute('transform') || '');
      bc = beads[bi].querySelector('circle');
      if (bm && bc) { var br = (parseFloat(bc.getAttribute('r')) || 8) + 3; seen.push([+bm[1] - br, +bm[2] - br, +bm[1] + br, +bm[2] + br]); }
    }
    var RR0 = (R.A && isFinite(R.A.R)) ? R.A.R : 0;
    /* v90：候选序——径向外推 k=0..8（每档先自然锚、再翻锚＝沿弧反向展开），再翻到主线带内侧 3 档；
     * 候选必须同时：不压珠/已放更替标签、完全在安全视口内、不压收起态竖签。k=0 自然锚能放下时与旧版逐字一致。 */
    function candH(o, rp, flip) {
      var s = PX(rp * Math.cos(o.a), rp * Math.sin(o.a)), s2 = PX(rp * Math.cos(o.a - 0.02), rp * Math.sin(o.a - 0.02));
      if (!s || !s2) return null;
      var deg = Math.atan2(s2[1] - s[1], s2[0] - s[0]) * 180 / Math.PI, anc = 'start';
      if (deg > 90 || deg < -90) { deg += 180; anc = 'end'; }
      if (flip) anc = anc === 'start' ? 'end' : 'start';
      var rad = deg * Math.PI / 180, cw = Math.cos(rad), sw = Math.sin(rad);
      /* SVG y=0 是文字基线，不是包围盒中心；基线偏移也要随文字旋转。 */
      var cxl = s[0] + (anc === 'start' ? 1 : -1) * cw * o.bw / 2 - sw * o.by;
      var cyl = s[1] + (anc === 'start' ? 1 : -1) * sw * o.bw / 2 + cw * o.by;
      var w2 = (Math.abs(cw) * o.bw + Math.abs(sw) * o.bh) / 2 + 2, h2 = (Math.abs(sw) * o.bw + Math.abs(cw) * o.bh) / 2 + 2;
      return { s: s, deg: deg, anc: anc, rc: [cxl - w2, cyl - h2, cxl + w2, cyl + h2] };
    }
    var rr = (R.A ? R.A.R : 0) + R.co, half = R.tk / 2;
    for (i = 0; i < R.T.length; i++) {
      o = R.T[i];
      V(o.el, !R.low);
      if (R.low) continue;
      var ca = Math.cos(o.a), sa = Math.sin(o.a);
      var p1 = PX((rr - half) * ca, (rr - half) * sa);
      var p2 = PX((rr + half) * ca, (rr + half) * sa);
      if (!p1 || !p2) { V(o.el, false); continue; }
      setIf(o.el, 'd', 'M' + n2(p1[0]) + ' ' + n2(p1[1]) + 'L' + n2(p2[0]) + ' ' + n2(p2[1]), '__clD');
    }
    var rn = rr + R.tk + R.fsC;
    for (i = 0; i < R.N.length; i++) {
      o = R.N[i];
      var q = PX(rn * Math.cos(o.a), rn * Math.sin(o.a));
      if (!q) { V(o.el, false); continue; }
      /* v90：章号是索引刻度，出了安全视口（或压到收起态竖签）就不画，不留半截数字 */
      var cw = estW(o.el.textContent || '', R.fsC) / 2 + 1, chh = R.fsC * 0.7 + 1;
      if (!fits([q[0] - cw, q[1] - chh, q[0] + cw, q[1] + chh])) { V(o.el, false); continue; }
      V(o.el, true);
      setIf(o.el, 'x', String(n2(q[0])), '__clX');
      setIf(o.el, 'y', String(n2(q[1])), '__clY');
      setIf(o.el, 'text-anchor', 'middle', '__clA');
    }
    /* 线名互斥：同扇区多条弧的沿弧名字两两不许相压——主线优先、其次事件数多者；输者折进账本（is-hidden） */
    {
      var cand = [], li, L1, rc1, kept = [];
      for (li = 0; li < R.LP.length; li++) { L1 = R.LP[li]; if ((!L1.short || L1.active) && L1.t) cand.push(L1); }
      cand.sort(function (p, q) { var pm = p.active ? -1 : p.rg.kind === 'main' ? 0 : 1, qm = q.active ? -1 : q.rg.kind === 'main' ? 0 : 1; return pm !== qm ? pm - qm : (q.rg.eventCount || 0) - (p.rg.eventCount || 0); });
      /* P1：包围盒来源——解析几何（已量度且已对账的标签）；否则真读（量度帧 / 对账帧 / 有字出路径）。
       * 真读前的写（V(true)）只对真读者做，并先于一切读完成；其余可见性在决定之后一次写。 */
      var mkey = metricKey(), db = dispBase(), needDisp = [], needMet = [], needDom = [];
      R.mkey = mkey;
      for (li = 0; li < cand.length; li++) {
        L1 = cand[li]; L1.dk = db + (L1.active ? '|a' : '|-');
        if (!L1.disp || L1.disp.key !== L1.dk) needDisp.push(L1);
      }
      if (needDisp.length) {
        for (li = 0; li < needDisp.length; li++) V(needDisp[li].t, true);
        for (li = 0; li < needDisp.length; li++) { needDisp[li].disp = { key: needDisp[li].dk, on: shown(needDisp[li].t) }; S.styleReads++; }
      }
      for (li = 0; li < cand.length; li++) {
        L1 = cand[li]; L1.rc = null;
        if (!L1.disp.on || !L1.pts || L1.pts.length < 2) { L1.rc = EMPTY; continue; }
        if (!L1.met || L1.met.key !== mkey) { needMet.push(L1); continue; }
        var am = metOf(L1), ar = am ? textRect(L1.pts, am) : null;
        if (ar) { L1.rc = ar; S.analytic++; } else needDom.push(L1);
      }
      if (needMet.length) measure(needMet, mkey);
      if (needMet.length || needDom.length) {
        var dom = needMet.concat(needDom);
        for (li = 0; li < dom.length; li++) V(dom[li].t, true);
        for (li = 0; li < dom.length; li++) { dom[li].rc = domRect(dom[li].t); S.fallback++; }
        /* 对账：解析值与真读 > CHECK_TOL 的标签本量度期内永久走真读 */
        for (li = 0; li < dom.length; li++) {
          var mt = dom[li].met;
          if (!mt || !mt.ok || mt.checked || dom[li].rc === EMPTY) continue;
          var chk = textRect(dom[li].pts, mt);
          if (!chk) continue;
          mt.checked = true;
          if (rectDiff(chk, dom[li].rc) > CHECK_TOL) { mt.ok = false; S.mismatch++; }
        }
      }
      for (li = 0; li < cand.length; li++) {
        L1 = cand[li]; L1.vis = true;
        rc1 = L1.rc;
        if (rc1 === EMPTY) continue;
        var clash = clashes(rc1, kept);
        /* v90：出画（不在安全视口）→ 先沿弧滑到画内的一段；互压仍按原规则直接折叠 */
        if (!clash && !fits(rc1)) {
          var alt = L1.short ? null : slideLabel(L1, kept);
          if (alt) { rc1 = alt; S.slid++; }
          else if (!L1.active) {
            L1.vis = false; anchorPath(L1, ''); hid++; S.folded++;
            arcMore(L1.rg, kept);
            continue;
          }
        }
        if (clash) { L1.vis = false; anchorPath(L1, ''); hid++; } else kept.push(rc1);
      }
      for (li = 0; li < cand.length; li++) V(cand[li].t, cand[li].vis);
    }
    /* v90：更替标签在线名之后落位——障碍 = 领衔珠 + 已保留的沿弧线名包围盒（旧序先放更替标签、线名互斥时看不到它，二者会叠字） */
    for (j = 0; j < kept.length; j++) seen.push(kept[j]);
    for (i = 0; i < R.H.length; i++) {
      o = R.H[i];
      if (!isFinite(o.a)) { V(o.el, false); hid++; continue; }
      if (!o.bw) { try { var bb = o.el.getBBox(); o.bw = bb.width || estW(o.txt, R.fsH); o.bh = bb.height || R.fsH * 1.4; o.by = bb.y + o.bh / 2; } catch (eB) { o.bw = estW(o.txt, R.fsH); o.bh = R.fsH * 1.4; o.by = -R.fsH * 0.35; } }
      var placed = false, k, f, cand, hit, rin = isFinite(o.r) && o.r > 0 ? o.r : RR0 * 0.965, plan = [];
      for (k = 0; k < 9; k++) { plan.push([(RR0 || o.r) + R.co + R.tk + R.fsC * 2.4 + k * R.fsH * 1.9, 0]); plan.push([plan[plan.length - 1][0], 1]); }
      for (k = 0; k < 3; k++) { plan.push([rin - R.notch - R.fsH * (0.9 + 1.9 * k), 0]); plan.push([plan[plan.length - 1][0], 1]); }
      for (f = 0; f < plan.length && !placed; f++) {
        cand = candH(o, plan[f][0], plan[f][1]);
        if (!cand) continue;
        hit = false;
        for (j = 0; j < seen.length; j++) if (inter(cand.rc, seen[j])) { hit = true; break; }
        if (hit || !fits(cand.rc)) continue;
        setIf(o.el, 'transform', 'translate(' + n2(cand.s[0]) + ',' + n2(cand.s[1]) + ') rotate(' + n2(cand.deg) + ')', '__clT');
        setIf(o.el, 'text-anchor', cand.anc, '__clA');
        V(o.el, true); seen.push(cand.rc); placed = true;
        if (plan[f][1] || f >= 18) S.flipped++;
      }
      if (!placed) {
        V(o.el, false); hid++; S.folded++;
        /* 折进账本：更替点留「…」标——主线带外侧 → 标签首档 → 主线带内侧，第一个落进安全视口且不压珠/标签者 */
        var mrs = [(RR0 || o.r) + R.co * 0.5, (RR0 || o.r) + R.co + R.tk + R.fsC * 2.4, rin - R.notch - R.fsH * 0.9], mi, mp;
        for (mi = 0; mi < mrs.length; mi++) {
          mp = PX(mrs[mi] * Math.cos(o.a), mrs[mi] * Math.sin(o.a));
          if (mp && moreMark(mp[0], mp[1], o.txt, seen)) break;
        }
      }
    }
    for (i = R.mUsed; i < R.M.length; i++) V(R.M[i], false);
    S.more = R.mUsed;
    S.hidden = hid;
  }
  function clashes(rc, list) {
    for (var k = 0; k < list.length; k++) if (inter(rc, list[k])) return true;
    return false;
  }
  /* v90「…」标：折进账本的标签在弧端/更替点留一枚省略号（带 <title> 全名，不承担交互）；只在安全视口内落位 */
  function moreMark(x, y, full, avoid) {
    var fs = R.fsL, rc = [x - fs * 0.7, y - fs * 0.7, x + fs * 0.7, y + fs * 0.7];
    if (!fits(rc) || clashes(rc, avoid)) return false;
    var e = R.M[R.mUsed];
    if (!e) {
      e = mk('text', 'cl-ann-label-more');
      e.setAttribute('text-anchor', 'middle');
      e.setAttribute('dominant-baseline', 'central');
      e.appendChild(document.createTextNode('…'));
      e.appendChild(mk('title'));
      R.g.appendChild(e); R.M.push(e);
    }
    R.mUsed++;
    setIf(e, 'x', String(n2(x)), '__clX'); setIf(e, 'y', String(n2(y)), '__clY');
    if (e.lastChild && e.lastChild.textContent !== full) e.lastChild.textContent = full;
    V(e, true); avoid.push(rc);
    return true;
  }
  function arcMore(rg, avoid) {
    var ends = [rg.a1, rg.a0], k, p0, p1, dx, dy, dl, lift = R.fsL * 0.9, dr = (R.A && R.A.R ? R.A.R : rg.r) * 0.03;
    for (k = 0; k < ends.length; k++) {
      if (!isFinite(ends[k])) continue;
      p0 = PX(rg.r * Math.cos(ends[k]), rg.r * Math.sin(ends[k]));
      p1 = PX((rg.r + dr) * Math.cos(ends[k]), (rg.r + dr) * Math.sin(ends[k]));
      if (!p0 || !p1) continue;
      dx = p1[0] - p0[0]; dy = p1[1] - p0[1]; dl = Math.sqrt(dx * dx + dy * dy) || 1;
      if (moreMark(p0[0] + dx / dl * lift, p0[1] + dy / dl * lift, String(rg.name || rg.shortName || ''), avoid)) return true;
    }
    return false;
  }
  function parsePts(d) {
    var segs = (d || '').replace(/^M/, '').split('L'), out = [], i, xy;
    for (i = 0; i < segs.length; i++) { xy = segs[i].trim().split(/[ ,]+/); if (xy.length >= 2 && isFinite(+xy[0]) && isFinite(+xy[1])) out.push([+xy[0], +xy[1]]); }
    return out;
  }
  /* 折线上按弧长截 [a,b] 一段（端点插值） */
  function subPts(pts, lens, a, b) {
    var out = [], i, t;
    for (i = 1; i < pts.length; i++) {
      var l0 = lens[i - 1], l1 = lens[i], d = l1 - l0;
      if (l1 < a || l0 > b || !(d > 0)) continue;
      if (!out.length) { t = Math.max(0, (a - l0) / d); out.push([pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t]); }
      if (l1 <= b) out.push(pts[i]);
      else { t = (b - l0) / d; out.push([pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t]); break; }
    }
    return out;
  }
  function ptsPath(pts) {
    var d = '', i;
    for (i = 0; i < pts.length; i++) d += (i ? 'L' : 'M') + n2(pts[i][0]) + ' ' + n2(pts[i][1]);
    return d;
  }
  /* v90 沿弧内收：在整条弧的投影折线上换一个落点，截出「字长 + 两端留白」的子路径让文字居中其上，
   * 正立方向按子路径中点切线重判（与旋转套件的正立判据同一口径）。成功返回新包围盒；失败复原路径返回 null。 */
  function slideLabel(item, kept) {
    var full = item.arc.getAttribute('d') || '', pts = parsePts(full);
    if (pts.length < 2) return null;
    var lens = [0], total = 0, i;
    for (i = 1; i < pts.length; i++) { total += Math.sqrt((pts[i][0] - pts[i - 1][0]) * (pts[i][0] - pts[i - 1][0]) + (pts[i][1] - pts[i - 1][1]) * (pts[i][1] - pts[i - 1][1])); lens.push(total); }
    /* P1：已对账的标签用解析几何试位（字长 = 量度得到的 W，即 getComputedTextLength 同值），只把最终落点写进 DOM；
     * 未量度/未对账/有字出路径的试位仍按旧法「写路径 → 真读」。 */
    var met = metOf(item), tl = 0;
    if (met) tl = met.W;
    else { try { tl = item.t.getComputedTextLength(); } catch (e) { tl = 0; } }
    if (!(tl > 0)) tl = estW(String(item.rg.shortName), R.fsL);
    var half = tl / 2 + R.gap, lo = half, hi = total - half;
    if (!(hi >= lo)) return null;
    var F = [0.36, 0.64, 0.22, 0.78, 0.1, 0.9, 0.02, 0.98], tried = [], f, c, sub, mid, rc, dup, j;
    for (f = 0; f < F.length; f++) {
      c = Math.max(lo, Math.min(hi, F[f] * total));
      dup = false;
      for (j = 0; j < tried.length; j++) if (Math.abs(tried[j] - c) < 6) { dup = true; break; }
      if (dup) continue;
      tried.push(c);
      sub = subPts(pts, lens, c - half, c + half);
      if (sub.length < 2) continue;
      var sl = [0], st2 = 0;
      for (j = 1; j < sub.length; j++) { st2 += Math.sqrt((sub[j][0] - sub[j - 1][0]) * (sub[j][0] - sub[j - 1][0]) + (sub[j][1] - sub[j - 1][1]) * (sub[j][1] - sub[j - 1][1])); sl.push(st2); }
      mid = 1;
      while (mid < sl.length - 1 && sl[mid] < st2 / 2) mid++;
      if (sub[mid][0] < sub[mid - 1][0]) sub.reverse();
      var d = ptsPath(sub), subR = [];
      for (j = 0; j < sub.length; j++) subR.push([n2(sub[j][0]), n2(sub[j][1])]);   /* DOM 解析 d 得到的就是 n2 值 */
      rc = met ? textRect(subR, met) : null;
      if (rc) {
        S.analytic++;
        if (fits(rc) && !clashes(rc, kept)) { item.lp.setAttribute('d', d); item.lastPath = d; item.pts = subR; return rc; }
        continue;
      }
      item.lp.setAttribute('d', d); item.lastPath = d; item.pts = subR;
      rc = domRect(item.t);
      if (rc === EMPTY) continue;
      if (fits(rc) && !clashes(rc, kept)) return rc;
    }
    /* 复原整弧路径（按既有正立规则） */
    var segs = full.replace(/^M/, '').split('L'), mm = 1, back = false;
    while (mm < lens.length - 1 && lens[mm] < total / 2) mm++;
    if (pts[mm] && pts[mm - 1] && pts[mm][0] < pts[mm - 1][0]) { segs.reverse(); full = 'M' + segs.join('L'); back = true; }
    item.lp.setAttribute('d', full); item.lastPath = full; item.pts = back ? pts.slice().reverse() : pts;
    return null;
  }
  function unmount() {
    if (document.fonts && document.fonts.removeEventListener) document.fonts.removeEventListener('loadingdone', fontsChanged);
    if (R.g && R.g.parentNode) R.g.parentNode.removeChild(R.g);
    R.g = null; R.rings = []; R.arcs = {}; R.H = []; R.T = []; R.N = []; R.LP = []; R.M = []; R.mUsed = 0; R.safe = null;
    R.layoutKey = null; R.projectXY = null; R.fontRevision = 0; R.metricRevision = null; R.mkey = null;
    safeUnbind();
    S.mounted = 0; S.labels = 0; S.handoffs = 0;
    S.ticks = 0; S.nums = 0; S.hidden = 0; S.lh = 0;
    S.layoutPasses = 0; S.frozenFrames = 0; S.rectReads = 0;
    S.analytic = 0; S.fallback = 0; S.metricPasses = 0; S.mismatch = 0; S.safeReads = 0; S.styleReads = 0;
  }
  function stats() {
    return {
      mounted: S.mounted, labels: S.labels, handoffs: S.handoffs,
      ticks: S.ticks, nums: S.nums, hidden: S.hidden,
      layoutPasses: S.layoutPasses, frozenFrames: S.frozenFrames, rectReads: S.rectReads,
      /* v90 出画治理计数：slid 沿弧内收次数 · flipped 更替标签翻锚/翻内侧 · folded 折叠 · more 当前「…」标数 · safe 本次安全区 */
      slid: S.slid, flipped: S.flipped, folded: S.folded, more: S.more, safe: R.safe ? R.safe.r.slice(0) : null, obstacles: R.safe ? R.safe.obs.length : 0,
      /* v90 P1 帧耗计数：analytic 解析包围盒次数 · fallback 真读（量度/对账/有字出路径）· metricPasses 克隆量度批次 ·
       * mismatch 对账超差被永久回退的标签数 · safeReads 安全区重读 · styleReads 显隐缓存未命中 */
      analytic: S.analytic, fallback: S.fallback, metricPasses: S.metricPasses, mismatch: S.mismatch, safeReads: S.safeReads, styleReads: S.styleReads,
      safeObs: R.safe ? R.safe.obs.map(function (o) { return o.slice(0); }) : []
    };
  }
  var plugin = { name: 'labels', mount: mount, frame: frame, unmount: unmount, stats: stats };
  window.CLAnnulusLabels = { name: 'labels', version: 'v90', plugin: plugin, stats: stats, safeBand: safeBand };
  function tryReg() {
    if (S.reg) return true;
    try {
      if (window.CLAnnulusSVG && typeof window.CLAnnulusSVG.use === 'function') {
        window.CLAnnulusSVG.use(plugin);
        S.reg = 1;
        return true;
      }
    } catch (e) {}
    return false;
  }
  if (!tryReg() && document.addEventListener) {
    document.addEventListener('cl:ann-ready', function () { tryReg(); });
    window.setTimeout(tryReg, 50);
  }
})();
