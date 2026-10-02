/* Castline · tree-timeline.js — 章节刻度条（window.CLTreeTimeline，v39）
 *
 * 【为什么是一条刻度，而不是又一块面板】
 * 树上亮着一根细枝时，用户需要知道「它在故事的第几段」。章是这部作品天然的横轴
 * （CLStory 的 chapters 就是按事件首次出现排的序），所以画一条 30 格的刻度、把当前章点亮，
 * 比写一段文字更省眼睛，也给「跳章」一个直接的落点。
 *
 * 【为什么不自己算章】
 * 章表、章的标题、每章事件数全部走 CLTreeEvents.chapters()（它读的还是 CLStory.get()）。
 * 本层不另存一份、不另排一次 —— 杜绝 v35「两把标尺」。
 *
 * 【纪律：沿用 tree-legend / tree-marks 的穿透口径（v38 定下，tree_qc F 组会查）】
 * 容器 #clTreeTimeline 是 pointer-events:none（整条刻度不挡树）；**只有刻点元素 pointer-events:auto**
 * （它们本来就是控件）。z-index 低于图例（12）与面板，位于底部、不占面板区域。
 *
 * 未就绪 / 无数据 → 整条静默不显示，绝不抛错。
 * 纪律：ES5 + IIFE + 'use strict'；禁 Math.random。
 */
(function () {
  'use strict';

  var ID = 'clTreeTimeline', CSS_ID = 'clTreeTimelineCss';
  var EVERY = 2;                        // 每 2 帧同步一次内容（章表/选中变化很慢）

  function tryFn(f) { try { return f(); } catch (e) { return null; } }
  function str(v) { return v == null ? '' : String(v); }

  var el = null, styleEl = null, trackEl = null, labelEl = null;
  var mounted = false, muted = false, shown = true, vis = false;
  var frame = 0, tickCount = 0, onCi = -1, lastLabel = '';

  var CSS =
    '#' + ID + '{position:fixed;left:50%;transform:translateX(-50%);bottom:44px;z-index:11;' +
    'display:flex;align-items:center;gap:12px;pointer-events:none;' +
    'font-family:var(--mono,ui-monospace,monospace);opacity:0;transition:opacity .34s}' +
    '#' + ID + '.on{opacity:1}' +
    '#' + ID + ' .lb{font-size:11px;letter-spacing:.12em;color:rgba(201,184,255,.72);' +
    'text-shadow:0 0 8px rgba(6,2,16,.92);white-space:nowrap}' +
    '#' + ID + ' .lb b{color:#efe6ff;font-weight:600}' +
    '#' + ID + ' .trk{display:flex;align-items:flex-end;gap:3px}' +
    '#' + ID + ' .tk{width:7px;height:11px;border-radius:1.5px;pointer-events:auto;cursor:pointer;' +
    'background:rgba(201,184,255,.22);box-shadow:inset 0 0 0 1px rgba(201,184,255,.18);' +
    'transition:background .18s,box-shadow .18s}' +
    '#' + ID + ' .tk:hover{background:rgba(255,180,92,.42)}' +
    '#' + ID + ' .tk.on{background:rgba(255,180,92,.92);box-shadow:0 0 8px rgba(255,180,92,.7)}' +
    '@media (prefers-reduced-motion:reduce){#' + ID + '{transition:none}#' + ID + ' .tk{transition:none}}';

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
    el.innerHTML = '<span class="lb"></span><span class="trk"></span>';
    labelEl = el.getElementsByClassName('lb')[0] || null;
    trackEl = el.getElementsByClassName('trk')[0] || null;
    el.addEventListener('click', onClick, false);          // 事件委托：重建刻点不丢监听
    document.body.appendChild(el);
    mounted = true;
    return true;
  }

  /** 刻点数量对齐章表：只在数量变了才重建 DOM（章是常量，正常只建一次）。 */
  function ensureTicks(n) {
    if (!trackEl || tickCount === n) return;
    var h = '', i;
    for (i = 0; i < n; i++) h += '<i class="tk" data-ci="' + i + '"></i>';
    trackEl.innerHTML = h;
    tickCount = n;
  }

  /** '第3章 南勘' → '南勘'；去不掉就直接用原名（不猜格式）。 */
  function chapterTitle(name) {
    var s = str(name).trim();
    var t = s.replace(/^第\s*[0-9]+\s*章\s*/, '');
    return t || s;
  }

  function refreshContent() {
    if (!el) return;
    var E = window.CLTreeEvents;
    if (!E || !E.chapters) return;
    var chs = tryFn(E.chapters) || [];
    ensureTicks(chs.length);

    var g = tryFn(E.get) || { evIdx: -1 };
    onCi = -1;
    if (g.evIdx >= 0 && E.info) {
      var nn = tryFn(function () { return E.info(g.evIdx); });
      if (nn) onCi = nn.chapIdx;
    }

    var label;
    if (onCi >= 0 && chs[onCi]) {
      var c = chs[onCi];
      label = '第 <b>' + (onCi + 1) + '</b> 章 · ' + chapterTitle(c.name) +
        (c.n ? ' · ' + c.n + ' 事件' : '');
    } else {
      label = '共 <b>' + chs.length + '</b> 章 · 点刻选事件';
    }
    if (labelEl && label !== lastLabel) { labelEl.innerHTML = label; lastLabel = label; }

    var ks = trackEl ? trackEl.getElementsByClassName('tk') : [], i;
    for (i = 0; i < ks.length; i++) {
      var on = (+ks[i].getAttribute('data-ci') === onCi);
      if (on !== ks[i].classList.contains('on')) ks[i].classList.toggle('on', on);
    }
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
    if (!el) return vis;
    el.classList.toggle('on', vis);
    return vis;
  }

  function update(s) {
    frame++;
    if (!mounted && !build()) return vis;
    if (s && s.muted !== undefined) muted = !!s.muted;
    if (frame % EVERY === 1) refreshContent();
    if (frame % EVERY === 0 || !vis) applyVis();
    return vis;
  }

  /* 点某章刻点 → 选中该章第一个事件（内部走 CLTreeEvents.pick，唯一入口）。 */
  function onClick(e) {
    if (!vis || !el) return;
    var t = e.target;
    var node = (t && t.closest) ? t.closest('.tk') : null;
    if (!node) {                                          // 兜底：向上爬 parentNode 找 .tk
      var n = t;
      while (n && n !== el && !(n.classList && n.classList.contains('tk'))) n = n.parentNode;
      node = (n && n !== el) ? n : null;
    }
    if (!node) return;
    var ci = +node.getAttribute('data-ci');
    if (!isFinite(ci)) return;
    var E = window.CLTreeEvents;
    if (!E || !E.firstOfChapter || !E.pick) return;
    var ev = tryFn(function () { return E.firstOfChapter(ci); });
    if (ev == null || ev < 0) return;                     // 该章没有事件：静默
    E.pick(ev);
    refreshContent();
  }

  function setOn(v) { muted = !v; return applyVis(); }
  function show(v) { shown = (v == null) ? true : !!v; return applyVis(); }
  function visible() { return !!vis; }

  function getProgress() {
    var E = window.CLTreeEvents;
    if (!E || !E.chapters) return 0.5;
    var chs = tryFn(E.chapters) || [];
    if (!chs.length) return 0.5;
    if (onCi >= 0) return Math.max(0, Math.min(1, (onCi + 0.5) / chs.length));
    return 0.5;
  }

  function stats() {
    return { mounted: mounted, visible: !!vis, muted: muted, shown: shown,
      chapters: tickCount, onChapter: onCi, progress: getProgress(), label: lastLabel, frame: frame };
  }

  var API = {
    name: 'tree-timeline',
    build: function () { build(); refreshContent(); return stats(); },
    update: update,
    dispose: function () {
      if (el && el.parentNode) el.parentNode.removeChild(el);
      el = null; labelEl = null; trackEl = null; mounted = false; tickCount = 0; lastLabel = '';
    },
    setOn: setOn,
    show: show,
    visible: visible,
    getProgress: getProgress,
    refresh: refreshContent,
    stats: stats
  };
  window.CLTreeTimeline = API;
  function hook() { if (window.CLArcana && window.CLArcana.register) window.CLArcana.register(API); }
  function boot() { build(); refreshContent(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); hook(); }, false);
  } else { boot(); hook(); }
})();
