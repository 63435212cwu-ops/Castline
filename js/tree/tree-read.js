/* tree-read.js —— 剧情线模式的极简读数条。
   为什么是「一行数字」：取代旧「剧情流」大框，只报事实、不占空间、不挡任何交互；
   为什么分段可缺：任何一项取不到就整段隐去（连同前面的分隔点），绝不用 0 冒充——
   读数条的价值就在于每个数字都真。 */
(function () {
  'use strict';

  var DIV_ID = 'clTreeRead';
  var CSS_ID = 'clTreeReadCss';
  var REFRESH_MS = 1000;   // 每秒刷一次足够；逐帧刷 DOM 是浪费
  var JUMP_STEPS = 8;      // 跳数动画：0.5s 内分 8 步到位
  var JUMP_MS = 500;

  var CSS =
    '#clTreeRead{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;z-index:13;' +
    'pointer-events:none;font-family:var(--mono,ui-monospace,monospace);font-size:11px;' +
    'letter-spacing:.14em;color:rgba(201,184,255,.78);text-shadow:0 0 8px rgba(6,2,16,.92);' +
    'white-space:nowrap;opacity:0;transition:opacity .34s}' +
    '#clTreeRead.cl-trd-on{opacity:1}' +
    '.cl-trd-n{color:#efe6ff;font-weight:600}' +
    '.cl-trd-dot{color:rgba(201,184,255,.34);padding:0 .6em}' +
    '@media (prefers-reduced-motion:reduce){#clTreeRead{transition:none}}';

  // 分段定义（顺序即显示顺序）：collect() 里同名 key 取到数才渲染该段
  var SEGS = [
    { key: 'trunkLen',  pre: '主干 ', post: ' 剧' },
    { key: 'trunkSegs', pre: '',      post: ' 段' },
    { key: 'handoffs',  pre: '换手 ', post: ' 次' },
    { key: 'branches',  pre: '支线 ', post: ' 条' },
    { key: 'coverage',  pre: '覆盖 ', post: '%' },
    { key: 'placed',    pre: '就位 ', post: ' 位' },
    { key: 'clones',    pre: '分身 ', post: '' }
  ];

  var el = null, styleEl = null, root = null;
  var numEls = {};          // key -> <b>，数字就地更新，避免整段重建
  var shown = {};           // key -> 当前显示值（跳数动画的起点）
  var jumps = {};           // key -> {from,to,i} 进行中的跳数
  var timer = null, jumpTimer = null, listening = false;
  var plotOn = null;        // cl:tree-plotline 明确给过才非 null：事件优先于状态推测
  var override = null;      // show() 手动强制；null = 不干预
  var lastS = null;         // update(s) 收到的状态；s.on === 0 视为聚焦态要淡出
  var reduce = false;       // prefers-reduced-motion：跳数直接到位
  var sig = '';             // 当前分段签名；只有分段增减才重建 DOM
  var curVisible = false, curFields = 0, curText = '';

  function isNum(v) { return typeof v === 'number' && isFinite(v); }
  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function tryFn(fn) { try { return fn(); } catch (e) { return null; } }

  // ---- 取数：全部守空；缺一段就少一段，宁缺勿编 ----
  function collect() {
    var v = {};
    var story = window.CLStory;
    var tree = story && typeof story.get === 'function' ? tryFn(story.get) : null;
    var t = tree ? tree.stats : null;
    if (typeof t === 'function') t = tryFn(t);
    if (t && typeof t === 'object') {
      if (isNum(t.trunkLen)) v.trunkLen = t.trunkLen;
      if (isNum(t.trunkSegs)) v.trunkSegs = t.trunkSegs;
      if (isNum(t.handoffs)) v.handoffs = t.handoffs;
      if (isNum(t.branches)) v.branches = t.branches;
      if (isNum(t.coverage)) v.coverage = Math.round(t.coverage * 100);
    }
    var mig = window.CLStarMigrate;
    if (mig && typeof mig.stats === 'function') {
      var ms = tryFn(mig.stats);
      if (ms && isNum(ms.placed)) v.placed = ms.placed;
    }
    var cc = window.CLCastClones;
    if (cc && typeof cc.stats === 'function') {
      var cs = tryFn(cc.stats);
      if (cs && isNum(cs.clones)) v.clones = cs.clones;
    }
    return v;
  }

  // CLStarMigrate.state() 可能直接回字符串，也可能回对象，两种都兼容
  function migInfo() {
    var out = { state: null, on: null };
    var m = window.CLStarMigrate;
    if (!m) return out;
    var s = typeof m.state === 'function' ? tryFn(m.state) : null;
    if (s == null && typeof m.stats === 'function') s = tryFn(m.stats);
    if (s == null) return out;
    if (typeof s === 'string') { out.state = s; return out; }
    if (typeof s === 'object') {
      if (typeof s.state === 'string') out.state = s.state;
      if (s.on === 0) out.on = 0;
    }
    return out;
  }

  function inPlotState() {
    var st = migInfo().state;
    return st === 'plot' || st === 'flying';
  }

  function focusBlocked() {
    if (lastS && lastS.on === 0) return true;
    if (migInfo().on === 0) return true;
    return false;
  }

  function applyVis() {
    var want;
    if (override !== null) want = override === true;
    else want = (plotOn === true || (plotOn === null && inPlotState())) && !focusBlocked();
    want = !!want && !!el;
    if (el) el.className = want ? 'cl-trd-on' : '';
    curVisible = want;
    return want;
  }

  function refreshText() { if (el) curText = el.textContent; }

  function setShown(key, val) {
    shown[key] = val;
    if (numEls[key]) numEls[key].textContent = String(val);
    refreshText();
  }

  function stepJumps() {
    var active = 0, k, j, v;
    for (k in jumps) {
      if (!has(jumps, k)) continue;
      j = jumps[k];
      j.i += 1;
      if (j.i >= JUMP_STEPS) { v = j.to; delete jumps[k]; }
      else { v = Math.round(j.from + (j.to - j.from) * (j.i / JUMP_STEPS)); active += 1; }
      setShown(k, v);
    }
    if (!active && jumpTimer) { clearInterval(jumpTimer); jumpTimer = null; }
  }

  function animateTo(key, to) {
    if (reduce || !numEls[key]) { setShown(key, to); return; }
    var from = has(shown, key) ? shown[key] : to;
    if (from === to) { setShown(key, to); return; }
    jumps[key] = { from: from, to: to, i: 0 };
    if (!jumpTimer) jumpTimer = setInterval(stepJumps, Math.round(JUMP_MS / JUMP_STEPS));
  }

  function rebuild(vals) {
    var html = '', i, s, first = true;
    for (i = 0; i < SEGS.length; i++) {
      s = SEGS[i];
      if (!has(vals, s.key)) continue;
      if (!first) html += '<span class="cl-trd-dot">·</span>';
      html += '<span class="cl-trd-seg">' + s.pre +
        '<b class="cl-trd-n" data-k="' + s.key + '">' + String(vals[s.key]) + '</b>' + s.post + '</span>';
      first = false;
    }
    el.innerHTML = html;
    jumps = {};           // 重建即对齐：作废进行中的跳数，避免旧动画污染新数字
    numEls = {}; shown = {};
    var bs = el.getElementsByTagName('b');
    for (i = 0; i < bs.length; i++) {
      var k = bs[i].getAttribute('data-k');
      numEls[k] = bs[i];
      shown[k] = vals[k]; // 首次出现不动画：没有旧值就没有「跳」可言
    }
    curFields = bs.length;
  }

  function refreshInternal(instant) {
    if (!el) return false;
    var vals = collect();
    var ns = '', i, s;
    for (i = 0; i < SEGS.length; i++) {
      s = SEGS[i];
      if (has(vals, s.key)) ns += s.key + ';';
    }
    if (ns !== sig) {
      sig = ns;
      rebuild(vals);
      refreshText();
    } else {
      for (i = 0; i < SEGS.length; i++) {
        s = SEGS[i];
        if (has(vals, s.key) && shown[s.key] !== vals[s.key]) {
          if (instant) { delete jumps[s.key]; setShown(s.key, vals[s.key]); }
          else animateTo(s.key, vals[s.key]);
        }
      }
    }
    return applyVis();
  }

  function tick() {
    if (window.CLSky && CLSky.enabled && CLSky.enabled()) { if (timer) { clearInterval(timer); timer = null; } return; }   /* 星空壳：旧剧情树读数不上屏 */
    refreshInternal(false);
  }
  function refresh() { return refreshInternal(true); } // 手动刷新即对齐到真值，不留给动画中间态

  function mount() {
    if (!styleEl && !document.getElementById(CSS_ID)) {
      styleEl = document.createElement('style');
      styleEl.id = CSS_ID;
      styleEl.textContent = CSS;
      (document.head || root).appendChild(styleEl);
    }
    var old = document.getElementById(DIV_ID);
    if (old && old.parentNode) old.parentNode.removeChild(old);
    el = document.createElement('div');
    el.id = DIV_ID;
    el.className = '';
    root.appendChild(el);
    sig = ''; numEls = {}; shown = {}; jumps = {};
    curFields = 0; curText = '';
    if (!timer) timer = setInterval(tick, REFRESH_MS);
    if (!listening) {
      document.addEventListener('cl:tree-plotline', onPlotline, false);
      listening = true;
    }
  }

  function build(o) {
    var mm = window.matchMedia;
    if (mm) {
      var q = tryFn(function () { return mm('(prefers-reduced-motion: reduce)'); });
      reduce = !!(q && q.matches);
    }
    if (o && typeof o === 'object') {
      if (o.root && typeof o.root.appendChild === 'function') root = o.root;
      else if (typeof o.appendChild === 'function') root = o;
    }
    if (!root) root = document.body || document.documentElement;
    mount();
    refreshInternal(true);
    return API;
  }

  function dispose() {
    if (jumpTimer) { clearInterval(jumpTimer); jumpTimer = null; }
    jumps = {};
    if (el && el.parentNode) el.parentNode.removeChild(el);
    el = null;
    if (styleEl && styleEl.parentNode) styleEl.parentNode.removeChild(styleEl);
    styleEl = null;
    var st = document.getElementById(CSS_ID);
    if (st && st.parentNode) st.parentNode.removeChild(st);
    if (timer) { clearInterval(timer); timer = null; }
    if (listening) {
      document.removeEventListener('cl:tree-plotline', onPlotline, false);
      listening = false;
    }
    numEls = {}; shown = {}; sig = '';
    plotOn = null; override = null; lastS = null;
    curVisible = false; curFields = 0; curText = '';
    root = null;
  }

  function onPlotline(e) {
    var d = e && e.detail ? e.detail : null;
    if (!d) return;                    // 没带明确开关就不猜
    if (d.on === true) plotOn = true;
    else if (d.on === false) plotOn = false;
    else return;
    applyVis();
  }

  function setOn(v) { plotOn = v === true; return applyVis(); }

  function show(v) {
    override = (v === null || typeof v === 'undefined') ? null : v === true;
    return applyVis();
  }

  function update(s) {
    lastS = (s && typeof s === 'object') ? s : null;
    return applyVis();
  }

  function visible() { return curVisible; }

  function stats() {
    return {
      mounted: !!el,
      visible: !!curVisible,
      fields: curFields,
      text: curText,
      muted: reduce === true
    };
  }

  var API = {
    name: 'tree-read',
    build: build, update: update, dispose: dispose, setOn: setOn,
    show: show, visible: visible, refresh: refresh, stats: stats
  };

  window.CLTreeRead = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }

  function boot() { build(null); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); hook(); }, false);
  } else { boot(); hook(); }
})();
