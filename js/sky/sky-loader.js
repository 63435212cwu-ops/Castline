/*!
 * @role loader
 * @owns js/sky/sky-loader.js
 * @budget drawcalls=0 points=0 vertices=0 rtpx=0 passes=0
 * @contract deep-sky/2
 *
 * 星空壳读取幕：深空底 + 书名 + 星盘刻度进度环 + 分阶段真实进度（读取 · 推演 · 排布 · 点亮 · 揭幕）；开篇语汇由 sky-loader-fx 挂上。
 * 纪律：ES5；不开 rAF / setInterval（纯 DOM 幕）；类名前缀 skd-；动态值只走 style.setProperty；文本走 textContent / esc()。
 * 环在主线程忙时照样转：旋转全由 CSS 关键帧作用在合成层，本文件只在阶段推进时写一次属性。
 */
(function (g) {
  'use strict';

  var SVGNS = 'http://www.w3.org/2000/svg';
  var VIEW = 280;                 /* = .skd-loader__dial 尺寸，由 CSS 令牌化 */
  var C = VIEW / 2;
  var R_OUT = 132;                /* 外细圆半径 */
  var TICKS = 72;                 /* 刻度数 */
  var TICK_EVERY = 6;             /* 每 6 个一根长刻度 */
  var R_TICK_SHORT = 125;
  var R_TICK_LONG = 116;
  var R_IN = 96;                  /* 内虚线圆半径 */
  var R_ARC = 114;                /* 进度弧半径 */
  var ARC_C = 2 * Math.PI * R_ARC;
  var SKIP_ON = 'reveal';

  var STEP_KEYS = ['fetch', 'analyze', 'layout', 'compile', 'reveal'];
  var STEP_TEXT = {
    fetch: '读取材料',
    analyze: '推演剧情线',
    layout: '排布星座',
    compile: '点亮光层',
    reveal: '揭幕'
  };

  function tok() { return g.CLSkyTokens || {}; }

  /* 离场时长取令牌 DUR.fly 的 3/4 秒（=900ms），不裸写毫秒 */
  function leaveMs() {
    var d = tok().DUR || {};
    var fly = typeof d.fly === 'number' ? d.fly : 1.2;
    return Math.round(fly * 1000 * 0.75);
  }

  function clamp01(v) {
    v = typeof v === 'number' && isFinite(v) ? v : 0;
    return v < 0 ? 0 : v > 1 ? 1 : v;
  }

  var U = g.CLSkyUtil, esc = U.esc;   /* 公共小工具（sky-util） */
  function setText(el, v) { el.textContent = v == null ? '' : String(v); }
  function el(tag, cls, parent) { return U.mk(tag, cls, parent); }

  function svg(tag, cls, parent) {
    var e = document.createElementNS(SVGNS, tag);
    if (cls) e.setAttribute('class', cls);
    if (parent) parent.appendChild(e);
    return e;
  }

  function attr(e, k, v) { e.setAttribute(k, String(v)); return e; }

  function circle(parent, r, extra) {
    var c = svg('circle', null, parent);
    attr(c, 'cx', C); attr(c, 'cy', C); attr(c, 'r', r);
    attr(c, 'fill', 'none');
    if (extra) { attr(c, 'stroke-width', extra.w); attr(c, 'stroke-dasharray', extra.d); }
    return c;
  }

  /* ---------- DOM 骨架 ---------- */

  function build(root) {
    var sky = el('div', 'skd-loader__sky', root);

    var body = el('div', 'skd-loader__body', root);   /* 盘与文字一组居中 */
    var dial = el('div', 'skd-loader__dial', body);

    var rOut = el('div', 'skd-loader__ring is-outer', dial);
    var sOut = svg('svg', 'skd-loader__svg', rOut);
    attr(sOut, 'viewBox', '0 0 ' + VIEW + ' ' + VIEW);
    attr(sOut, 'aria-hidden', 'true');
    attr(sOut, 'focusable', 'false');
    circle(sOut, R_OUT, { w: 1, d: '' });
    var i, a, x1, y1, x2, y2, ln;
    for (i = 0; i < TICKS; i++) {
      a = (i / TICKS) * Math.PI * 2;
      var long = (i % TICK_EVERY) === 0;
      var r2 = long ? R_TICK_LONG : R_TICK_SHORT;
      x1 = C + R_OUT * Math.sin(a); y1 = C - R_OUT * Math.cos(a);
      x2 = C + r2 * Math.sin(a); y2 = C - r2 * Math.cos(a);
      ln = svg('line', long ? 'skd-loader__tick is-long' : 'skd-loader__tick', sOut);
      attr(ln, 'x1', x1.toFixed(2)); attr(ln, 'y1', y1.toFixed(2));
      attr(ln, 'x2', x2.toFixed(2)); attr(ln, 'y2', y2.toFixed(2));
      if (long) attr(ln, 'stroke-width', 2);
    }

    var rIn = el('div', 'skd-loader__ring is-inner', dial);
    var sIn = svg('svg', 'skd-loader__svg', rIn);
    attr(sIn, 'viewBox', '0 0 ' + VIEW + ' ' + VIEW);
    attr(sIn, 'aria-hidden', 'true');
    attr(sIn, 'focusable', 'false');
    circle(sIn, R_IN, { w: 1, d: '2 6' });

    var sArc = svg('svg', 'skd-loader__arc', dial);
    attr(sArc, 'viewBox', '0 0 ' + VIEW + ' ' + VIEW);
    attr(sArc, 'aria-hidden', 'true');
    attr(sArc, 'focusable', 'false');
    attr(sArc, 'role', 'progressbar');
    attr(sArc, 'aria-valuemin', 0);
    attr(sArc, 'aria-valuemax', 1);
    var arc = svg('circle', null, sArc);
    attr(arc, 'cx', C); attr(arc, 'cy', C); attr(arc, 'r', R_ARC);
    attr(arc, 'fill', 'none');
    attr(arc, 'stroke-width', 3);
    attr(arc, 'stroke-linecap', 'round');
    attr(arc, 'stroke-dasharray', ARC_C.toFixed(2));
    attr(arc, 'stroke-dashoffset', ARC_C.toFixed(2));
    attr(arc, 'transform', 'rotate(-90 ' + C + ' ' + C + ')');

    el('div', 'skd-loader__core', dial);

    var box = el('div', 'skd-loader__text', body);
    var title = el('div', 'skd-loader__title', box);
    var sub = el('div', 'skd-loader__sub', box);
    var stage = el('div', 'skd-loader__stage', box);
    var detail = el('div', 'skd-loader__detail', box);

    var ol = el('ol', 'skd-loader__steps', box);
    var html = '', k;
    for (k = 0; k < STEP_KEYS.length; k++) {
      html += '<li class="skd-loader__step" data-k="' + esc(STEP_KEYS[k]) + '">' +
        esc(STEP_TEXT[STEP_KEYS[k]]) + '</li>';
    }
    ol.innerHTML = html;

    var skip = el('div', 'skd-loader__skip', root);   /* 贴视口底边（放在文字组里会压住阶段名） */
    setText(skip, '点击或按任意键跳过揭幕');

    return {
      sky: sky, dial: dial, arc: arc, sArc: sArc,
      title: title, sub: sub, stage: stage, detail: detail,
      items: ol.getElementsByTagName('li'), skip: skip
    };
  }

  /* ---------- 实例 ---------- */

  function create(opts) {
    opts = opts || {};
    var st = {
      shown: false, stage: '', frac: 0, done: [],
      timer: 0, cb: null, skipBound: false, dead: false,
      onSkip: typeof opts.onSkip === 'function' ? opts.onSkip : null
    };
    var reducedMotion = false;   /* reduced(): 一切过渡直达终态、循环动画停 */
    var self;

    var root = el('div', 'skd-loader');
    attr(root, 'role', 'status');
    attr(root, 'aria-live', 'polite');
    attr(root, 'hidden', 'hidden');
    var host = opts.host || document.body;
    host.appendChild(root);
    var dom = build(root);
    /* 开篇语汇（sky-loader-fx）；缺席时读取幕照旧 */
    var fx = g.CLSkyLoaderFx ? g.CLSkyLoaderFx.attach(root, dom) : null;

    function reduced() {
      return typeof tok().reduced === 'function' ? !!tok().reduced() : false;
    }

    function paintArc() {
      var f = clamp01(st.frac);
      dom.arc.setAttribute('stroke-dashoffset', (ARC_C * (1 - f)).toFixed(2));
      dom.arc.setAttribute('aria-valuenow', f.toFixed(3));
      root.style.setProperty('--p', f.toFixed(4));
    }

    function markSteps(key) {
      var idx = -1, i, li, d = [];
      for (i = 0; i < STEP_KEYS.length; i++) { if (STEP_KEYS[i] === key) { idx = i; } }
      for (i = 0; i < dom.items.length; i++) {
        li = dom.items[i];
        if (idx >= 0 && i < idx) {
          li.className = 'skd-loader__step is-done'; d.push(li.getAttribute('data-k'));
        } else if (i === idx) {
          li.className = 'skd-loader__step is-now';
        } else {
          li.className = 'skd-loader__step';
        }
      }
      st.done = d;
    }

    function unbindSkip() {
      if (!st.skipBound) { return; }
      st.skipBound = false;
      document.removeEventListener('click', onSkipEvt, true);
      document.removeEventListener('keydown', onSkipEvt, true);
    }

    function onSkipEvt(e) {
      unbindSkip();
      if (st.onSkip) { st.onSkip(e); }
    }

    function bindSkip() {
      if (st.skipBound || !st.onSkip || st.dead) { return; }
      st.skipBound = true;
      document.addEventListener('click', onSkipEvt, true);
      document.addEventListener('keydown', onSkipEvt, true);
    }

    function teardown() {
      if (st.timer) { clearTimeout(st.timer); st.timer = 0; }
      unbindSkip();
      dom.skip.className = 'skd-loader__skip';
      root.className = 'skd-loader' + (fx ? ' is-cine' : '');
      root.setAttribute('hidden', 'hidden');
      if (fx && fx.rain) fx.rain.clear();
      st.shown = false;
    }

    function show(meta) {
      meta = meta || {};
      reducedMotion = reduced();
      if (st.timer) { clearTimeout(st.timer); st.timer = 0; }
      st.stage = '';
      st.frac = 0;
      st.done = [];
      st.shown = true;
      setText(dom.title, meta.title);
      setText(dom.sub, meta.sub);
      setText(dom.stage, '');
      setText(dom.detail, '');
      markSteps('');
      paintArc();
      unbindSkip();
      dom.skip.className = 'skd-loader__skip';
      root.removeAttribute('hidden');
      /* instant：开机幕底立刻不透明（旧外围不透出），只让盘与文字淡入；否则下一拍加 is-on 让入场过渡真的跑 */
      var base = meta.instant ? 'skd-loader is-instant' : 'skd-loader';
      root.className = base + (fx ? ' is-cine' : '');
      if (fx) fx.show(meta);
      setTimeout(function () {
        if (st.dead || !st.shown) { return; }
        root.className = base + (fx ? ' is-cine' : '') + ' is-on';
      }, 0);
    }

    function stage_(key, frac, detail) {
      if (st.dead) { return; }
      var f = clamp01(frac);
      if (f > st.frac) { st.frac = f; }
      paintArc();
      if (key) {
        st.stage = key;
        setText(dom.stage, STEP_TEXT[key] || key);
      }
      setText(dom.detail, detail);
      markSteps(key);
      if (fx) fx.stage(key, st.frac, detail);
      if (key === SKIP_ON) {
        dom.skip.className = 'skd-loader__skip is-on';
        bindSkip();
      } else {
        dom.skip.className = 'skd-loader__skip';
        unbindSkip();
      }
    }

    function done(cb) {
      if (st.dead) { return; }
      st.frac = 1;
      paintArc();
      st.stage = 'done';
      markSteps(SKIP_ON);
      setText(dom.stage, STEP_TEXT[SKIP_ON]);
      if (fx) fx.finish();
      unbindSkip();
      dom.skip.className = 'skd-loader__skip';
      st.cb = typeof cb === 'function' ? cb : null;
      reducedMotion = reduced();
      if (reducedMotion) {
        teardown();
        if (st.cb) { var c0 = st.cb; st.cb = null; c0(); }
        return;
      }
      root.className = 'skd-loader' + (fx ? ' is-cine' : '') + ' is-on is-leaving';
      st.timer = setTimeout(function () {
        st.timer = 0;
        teardown();
        if (st.cb) { var c1 = st.cb; st.cb = null; c1(); }
      }, leaveMs());
    }

    /* 书名晚到（数据链接要读完才知道标题）时补写 */
    function title(t, sub) {
      if (st.dead) { return; }
      if (t != null) { if (fx) fx.title(t); else setText(dom.title, t); }
      if (sub != null) { setText(dom.sub, sub); }
    }

    function hide() { teardown(); }

    function stats() {
      return {
        shown: !!st.shown,
        stage: st.stage,
        frac: clamp01(st.frac),
        done: st.done.slice(0),
        fx: fx ? fx.stats() : null
      };
    }

    function dispose() {
      if (st.dead) { return; }
      st.dead = true;
      teardown();
      st.cb = null;
      st.onSkip = null;
      if (root.parentNode) { root.parentNode.removeChild(root); }
      root = null; dom = null;
    }

    /* 低端档：零 GL 资源；开篇语汇降为静态（CSS / fx 各自处理） */
    function setTier(tier) { if (fx) fx.setTier(tier); root.setAttribute('data-tier', tier || 'high'); }
    /* 开篇数据流：真实读数进日志 / 角标，字符雨换书中文字；holdLeft = 书名与日志还差多久打完 */
    function log(line) { return fx && !st.dead ? fx.log(line) : 0; }
    function counts(o) { if (fx && !st.dead) fx.counts(o); }
    function glyphs(list) { return fx && !st.dead ? fx.glyphs(list) : 0; }
    function holdLeft() { return fx && st.shown ? fx.holdLeft() : 0; }

    self = {
      show: show,
      stage: stage_,
      done: done,
      title: title,
      hide: hide,
      stats: stats,
      dispose: dispose,
      setTier: setTier,
      log: log,
      counts: counts,
      glyphs: glyphs,
      holdLeft: holdLeft
    };
    return self;
  }

  g.CLSkyLoader = { create: create };
})(window);
