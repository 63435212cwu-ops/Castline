/* Castline · tree-event-card.js — 事件详情卡（window.CLTreeEventCard，v39）
 *
 * 【为什么要有它】
 * 树上点亮一根细枝（CLTreeFocus.solo）之后，「这条事件到底讲了什么」必须能被读到：
 * 标题、第几章、原句引文、参与了谁。它是 v39「树 = 可逐条读取的故事索引」的下半句 ——
 * 上半句是刻度条（tree-timeline），下半句是这张卡。
 *
 * 【穿透与可点（沿用 v38 定的口径）】
 * 容器 #clTreeEventCard 是 pointer-events:none（卡片本体不挡树、不占面板的鼠标）；
 * **只有「上一条 / 下一条」两个按钮 pointer-events:auto**。z-index 低于既有面板。
 *
 * 【一个真相】
 * 内容全部来自 CLTreeEvents.get() / CLTreeEvents.info()（那份数据还是 CLStory.get()）。
 * 本层不自己存事件、不自己算章。无选中 → 整卡从 DOM 上隐藏（display:none），不是只改内部状态。
 *
 * 纪律：ES5 + IIFE + 'use strict'；禁 Math.random。
 */
(function () {
  'use strict';

  var ID = 'clTreeEventCard', CSS_ID = 'clTreeEventCardCss';
  var EVERY = 2;

  function tryFn(f) { try { return f(); } catch (e) { return null; } }
  function str(v) { return v == null ? '' : String(v); }

  var el = null, styleEl = null, mounted = false, muted = false, shown = true, vis = false;
  var dotEl = null, kindEl = null, chEl = null, tiEl = null, qtEl = null, csEl = null,
    srcEl = null, metaEl = null, posEl = null;
  var frame = 0, curKey = '', curOn = false;

  var CSS =
    '#' + ID + '{position:fixed;right:22px;bottom:88px;width:250px;z-index:12;pointer-events:none;' +
    'display:none;padding:10px 12px 9px;border-radius:4px;border:1px solid rgba(255,180,92,.24);' +
    'background:linear-gradient(180deg,rgba(10,7,20,.86),rgba(10,7,20,.62));' +
    '-webkit-backdrop-filter:blur(7px);backdrop-filter:blur(7px);' +
    'box-shadow:0 0 20px rgba(6,2,16,.7);color:#efe6ff}' +
    '#' + ID + '.on{display:block}' +
    '#' + ID + ' .hd{display:flex;align-items:center;gap:7px;margin-bottom:6px;' +
    'font-family:var(--mono,ui-monospace,monospace);font-size:11px;letter-spacing:.12em}' +
    '#' + ID + ' .hd i{width:7px;height:7px;border-radius:50%;flex:0 0 auto}' +
    '#' + ID + ' .hd .kd{color:rgba(239,230,255,.9)}' +
    '#' + ID + ' .hd .ch{margin-left:auto;color:rgba(201,184,255,.62)}' +
    '#' + ID + ' .ti{font-size:13px;line-height:1.35;font-weight:600;letter-spacing:.02em;margin-bottom:5px}' +
    '#' + ID + ' .qt{font-size:11px;line-height:1.5;color:rgba(239,230,255,.72);' +
    'border-left:2px solid rgba(255,180,92,.42);padding-left:8px;margin-bottom:5px}' +
    '#' + ID + ' .cs{font-size:11px;line-height:1.45;color:rgba(201,184,255,.72)}' +
    '#' + ID + ' .src{font-size:11px;line-height:1.4;margin-top:5px;color:rgba(255,180,92,.72)}' +
    '#' + ID + ' .meta{font-size:11px;line-height:1.4;margin-top:2px;color:rgba(201,184,255,.5)}' +
    '#' + ID + ' .nav{display:flex;align-items:center;gap:8px;margin-top:8px;' +
    'padding-top:7px;border-top:1px solid rgba(172,156,230,.16)}' +
    '#' + ID + ' .nav b{flex:1 1 auto;text-align:center;font-weight:400;font-size:11px;' +
    'font-family:var(--mono,ui-monospace,monospace);color:rgba(201,184,255,.5)}' +
    '#' + ID + ' .nav button{pointer-events:auto;cursor:pointer;font:inherit;font-size:11px;' +
    'line-height:1.25;padding:3px 9px;border-radius:3px;border:1px solid rgba(255,180,92,.3);' +
    'background:rgba(255,180,92,.08);color:#ffd9a0}' +
    '#' + ID + ' .nav button:hover{background:rgba(255,180,92,.16);color:#fff}' +
    '#' + ID + ' .qt.off{display:none}';

  function css() {
    if (document.getElementById(CSS_ID)) return;
    styleEl = document.createElement('style');
    styleEl.id = CSS_ID;
    styleEl.textContent = CSS;
    document.head.appendChild(styleEl);
  }

  function build() {
    if (mounted) return true;
    if (!document.body) return false;
    css();
    el = document.createElement('div');
    el.id = ID;
    el.innerHTML =
      '<div class="hd"><i class="dot"></i><span class="kd"></span><span class="ch"></span></div>' +
      '<div class="ti"></div><div class="qt off"></div><div class="cs"></div>' +
      '<div class="src"></div><div class="meta"></div>' +
      '<div class="nav"><button class="pv" type="button">上一条</button>' +
      '<b class="pos"></b><button class="nx" type="button">下一条</button></div>';
    dotEl = el.getElementsByClassName('dot')[0] || null;
    kindEl = el.getElementsByClassName('kd')[0] || null;
    chEl = el.getElementsByClassName('ch')[0] || null;
    tiEl = el.getElementsByClassName('ti')[0] || null;
    qtEl = el.getElementsByClassName('qt')[0] || null;
    csEl = el.getElementsByClassName('cs')[0] || null;
    srcEl = el.getElementsByClassName('src')[0] || null;
    metaEl = el.getElementsByClassName('meta')[0] || null;
    posEl = el.getElementsByClassName('pos')[0] || null;
    el.addEventListener('click', onClick, false);          // 委托：内容重建不丢监听
    document.body.appendChild(el);
    mounted = true;
    return true;
  }

  function setText(node, s) { if (node && node.textContent !== s) node.textContent = s; }

  /* 完整度：来源没给出就是「未知」，绝不显示编造的百分比。 */
  function completionText(info) {
    if (!info || info.completionKnown !== true || info.completion == null || !isFinite(+info.completion)) return '未知';
    var c = +info.completion;
    return (c >= 0 && c <= 1) ? Math.round(c * 100) + '%' : String(c);
  }

  function refreshContent() {
    if (!el) return;
    var E = window.CLTreeEvents;
    if (!E || !E.get) return;
    var g = tryFn(E.get) || { evIdx: -1 };
    if (g.evIdx < 0) {                                     // 无选中：整卡落 DOM 隐藏
      if (curOn) { el.classList.remove('on'); curOn = false; curKey = ''; }
      return;
    }
    var info = (E.info) ? tryFn(function () { return E.info(g.evIdx); }) : null;
    if (!info) { if (curOn) { el.classList.remove('on'); curOn = false; } return; }

    var key = info.evIdx + '|' + info.kind + '|' + info.title + '|' + info.chapter + '|' +
      info.quote + '|' + info.characters.join(',') + '|' + str(info.source) + '|' +
      str(info.threadId) + '|' + str(info.line) + '|' + str(info.status) + '|' + info.len + '|' +
      info.completionKnown + '|' + info.completion;
    if (key !== curKey) {
      curKey = key;
      var P = window.CLPalette;
      var c = (P && P.css) ? P.css(info.kind) : '#ffb45c';
      if (dotEl) { dotEl.style.background = c; dotEl.style.boxShadow = '0 0 7px ' + c; }
      setText(kindEl, info.kind);
      setText(chEl, info.chapter);
      setText(tiEl, info.title);
      setText(csEl, info.characters.join('、'));
      /* 来源标注：模型抽取不是原文已验证，只写「来源」+ 是否待校对，不称确证。 */
      var srcTxt = '来源 ' + str(info.source) + (info.status === 'confirmed' ? ' · 边已确认' : ' · 待校对');
      setText(srcEl, srcTxt);
      /* 长度＝事件步数；完整度只在来源给出时表达，未知不显示百分比。 */
      var bits = [];
      if (info.line) bits.push('线 ' + info.line);
      bits.push('长度 ' + Math.floor(+info.len || 0) + ' 事件步');
      bits.push('完整度 ' + completionText(info));
      setText(metaEl, bits.join(' · '));
      var q = str(info.quote).trim();
      if (qtEl) {
        setText(qtEl, q);
        qtEl.classList.toggle('off', !q);                 // 无引文就整行收起，不留空框
      }
      var dom = (E.domain) ? (tryFn(E.domain) || []) : [];
      var at = -1, i;
      for (i = 0; i < dom.length; i++) if (dom[i] === info.evIdx) { at = i; break; }
      setText(posEl, (at >= 0 ? (at + 1) : '?') + ' / ' + dom.length);
    }
    if (!curOn) { el.classList.add('on'); curOn = true; }
  }

  function treeShown() {
    var S = window.CLTreeStage;
    if (!S || !S.stats) return false;
    var ss = tryFn(S.stats);
    return !!(ss && ss.active);
  }
  function eventsReady() {
    var E = window.CLTreeEvents;
    if (!E || !E.stats) return false;
    var s = tryFn(E.stats);
    return !!(s && s.ready);
  }

  function applyVis() {
    var want = shown && !muted && treeShown() && eventsReady();
    vis = !!want;
    if (!vis && el && curOn) { el.classList.remove('on'); curOn = false; }
    return vis;
  }

  function update(s) {
    frame++;
    if (!mounted && !build()) return vis;
    if (s && s.muted !== undefined) muted = !!s.muted;
    if (frame % EVERY === 1) { applyVis(); refreshContent(); }
    else if (frame % EVERY === 0) applyVis();
    return vis;
  }

  function onClick(e) {
    var t = e.target;
    var cls = (t && t.className) ? String(t.className) : '';
    var isPrev = cls.indexOf('pv') >= 0, isNext = cls.indexOf('nx') >= 0;
    if (!isPrev && !isNext) return;
    var E = window.CLTreeEvents;
    if (!E) return;
    if (isPrev && E.prev) tryFn(function () { return E.prev(); });
    else if (isNext && E.next) tryFn(function () { return E.next(); });
    refreshContent();
  }

  function setOn(v) { muted = !v; return applyVis(); }
  function show(v) { shown = (v == null) ? true : !!v; return applyVis(); }
  function visible() { return !!vis && !!curOn; }

  /* 拾取层用来防穿透：卡片可见时，落在卡片矩形内的屏幕点归卡片，不算画布拾取。 */
  function hitTest(x, y) {
    if (!el || !curOn) return false;
    var r;
    try { r = el.getBoundingClientRect(); } catch (e) { return false; }
    if (!r || !r.width || !r.height) return false;
    return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
  }

  function stats() {
    return { mounted: mounted, visible: !!vis, on: !!curOn, muted: muted, shown: shown,
      evIdx: (window.CLTreeEvents && window.CLTreeEvents.get) ? ((tryFn(window.CLTreeEvents.get) || {}).evIdx) : -1,
      title: tiEl ? tiEl.textContent : '', chapter: chEl ? chEl.textContent : '',
      characters: csEl ? csEl.textContent : '', quote: qtEl ? (qtEl.classList.contains('off') ? '' : qtEl.textContent) : '',
      source: srcEl ? srcEl.textContent : '', meta: metaEl ? metaEl.textContent : '',
      frame: frame };
  }

  var API = {
    name: 'tree-event-card',
    build: function () { build(); refreshContent(); return stats(); },
    update: update,
    dispose: function () {
      if (el && el.parentNode) el.parentNode.removeChild(el);
      el = null; mounted = false; curOn = false; curKey = '';
    },
    setOn: setOn,
    show: show,
    visible: visible,
    refresh: refreshContent,
    hitTest: hitTest,
    stats: stats
  };
  window.CLTreeEventCard = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  function boot() { build(); refreshContent(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); hook(); }, false);
  } else { boot(); hook(); }
})();
